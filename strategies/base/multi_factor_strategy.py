"""
多因子策略基类
支持多因子选股和分层回测
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date
import backtrader as bt

from .base_strategy import BaseStrategy


class MultiFactorStrategy(BaseStrategy):
    """
    多因子策略基类
    支持：
    - 多因子打分选股
    - 行业中性化
    - 市值分层
    - 因子权重配置
    """
    
    params = (
        # 继承基础参数
        *BaseStrategy.params,
        
        # 多因子特有参数
        ('factor_weights', {}),        # 因子权重字典 {'factor_name': weight}
        ('factor_direction', {}),       # 因子方向 {'factor_name': 1/-1}
        ('stock_pool', None),          # 股票池（None表示全市场）
        ('top_n', 20),                 # 选股数量
        ('rebalance_freq', 'M'),       # 调仓频率：D-日 W-周 M-月
        ('industry_neutral', False),   # 是否行业中性
        ('cap_neutral', False),        # 是否市值中性
        ('industry_deviation', 0.05),  # 行业偏离度限制
        ('cap_group', None),           # 市值分组：large/mid/small/micro
    )
    
    def __init__(self):
        super().__init__()
        
        # 多因子数据
        self.factor_data = {}
        self.stock_scores = {}
        
        # 调仓管理
        self.last_rebalance_date = None
        self.current_holdings = []
        
        # 分层信息
        self.industry_info = {}
        self.cap_group_info = {}
    
    def load_factor_data(self, factor_df: pd.DataFrame):
        """
        加载因子数据
        
        Args:
            factor_df: 因子DataFrame，包含date, code, factor1, factor2...
        """
        # 按日期分组存储
        for date_val, group in factor_df.groupby('date'):
            self.factor_data[date_val] = group.set_index('code')
    
    def calculate_factor_scores(
        self,
        date: date,
        factors: Optional[List[str]] = None
    ) -> pd.Series:
        """
        计算因子得分
        
        Args:
            date: 计算日期
            factors: 使用的因子列表，None表示使用所有配置因子
        
        Returns:
            股票得分Series
        """
        if date not in self.factor_data:
            return pd.Series()
        
        df = self.factor_data[date]
        
        # 确定使用的因子
        if factors is None:
            factors = list(self.params.factor_weights.keys())
        
        if not factors:
            return pd.Series()
        
        # 计算每个因子的得分
        factor_scores = pd.DataFrame(index=df.index)
        
        for factor in factors:
            if factor not in df.columns:
                continue
            
            # 获取因子方向（正向/反向）
            direction = self.params.factor_direction.get(factor, 1)
            weight = self.params.factor_weights.get(factor, 1.0)
            
            # 去极值（MAD法）
            factor_values = self._winsorize_mad(df[factor])
            
            # 标准化（Z-score）
            factor_values = (factor_values - factor_values.mean()) / factor_values.std()
            
            # 应用方向
            factor_values = factor_values * direction
            
            # 应用权重
            factor_scores[factor] = factor_values * weight
        
        # 计算综合得分
        total_score = factor_scores.sum(axis=1)
        
        return total_score.sort_values(ascending=False)
    
    def _winsorize_mad(self, series: pd.Series, n: int = 3) -> pd.Series:
        """MAD去极值"""
        median = series.median()
        mad = (series - median).abs().median()
        upper = median + n * 1.4826 * mad
        lower = median - n * 1.4826 * mad
        return series.clip(lower, upper)
    
    def select_stocks(
        self,
        date: date,
        top_n: Optional[int] = None
    ) -> List[str]:
        """
        选股
        
        Args:
            date: 选股日期
            top_n: 选股数量，None使用参数配置
        
        Returns:
            选中的股票代码列表
        """
        if top_n is None:
            top_n = self.params.top_n
        
        # 计算得分
        scores = self.calculate_factor_scores(date)
        
        if len(scores) == 0:
            return []
        
        selected = []
        
        # 行业中性化选股
        if self.params.industry_neutral and self.industry_info:
            selected = self._industry_neutral_selection(scores, date, top_n)
        else:
            # 简单取top N
            selected = scores.head(top_n).index.tolist()
        
        # 市值分组筛选
        if self.params.cap_group and self.cap_group_info:
            selected = self._filter_by_cap_group(selected, date)
        
        return selected
    
    def _industry_neutral_selection(
        self,
        scores: pd.Series,
        date: date,
        top_n: int
    ) -> List[str]:
        """行业中性化选股"""
        # 获取行业分布
        industry_dist = self._get_industry_distribution(date)
        
        # 计算每个行业应选数量
        industry_quota = {}
        for industry, pct in industry_dist.items():
            industry_quota[industry] = max(1, int(top_n * pct))
        
        # 按行业选取得分最高的股票
        selected = []
        df = self.factor_data.get(date, pd.DataFrame())
        
        for industry, quota in industry_quota.items():
            industry_stocks = df[df['industry'] == industry].index
            industry_scores = scores[scores.index.isin(industry_stocks)]
            
            selected.extend(industry_scores.head(quota).index.tolist())
            
            if len(selected) >= top_n:
                break
        
        return selected[:top_n]
    
    def _get_industry_distribution(self, date: date) -> Dict[str, float]:
        """获取行业分布"""
        # 这里简化处理，实际应该根据基准指数计算
        # 返回各行业的市值占比
        df = self.factor_data.get(date, pd.DataFrame())
        
        if 'industry' not in df.columns:
            return {}
        
        industry_counts = df['industry'].value_counts(normalize=True)
        return industry_counts.to_dict()
    
    def _filter_by_cap_group(self, stocks: List[str], date: date) -> List[str]:
        """按市值分组筛选"""
        df = self.factor_data.get(date, pd.DataFrame())
        
        if 'cap_group' not in df.columns:
            return stocks
        
        target_group = self.params.cap_group
        filtered = df[
            (df.index.isin(stocks)) & 
            (df['cap_group'] == target_group)
        ].index.tolist()
        
        return filtered
    
    def should_rebalance(self, current_date: date) -> bool:
        """检查是否需要调仓"""
        if self.last_rebalance_date is None:
            return True
        
        freq = self.params.rebalance_freq
        
        if freq == 'D':  # 每日调仓
            return True
        elif freq == 'W':  # 每周调仓
            return current_date.weekday() == 0  # 周一调仓
        elif freq == 'M':  # 每月调仓
            return current_date.day == 1  # 月初调仓
        
        return False
    
    def generate_signals(self) -> Dict[str, Any]:
        """
        生成交易信号（多因子版本）
        """
        current_date = self.datas[0].datetime.date(0)
        
        # 检查是否需要调仓
        if not self.should_rebalance(current_date):
            return {'action': 'HOLD'}
        
        # 选股
        selected_stocks = self.select_stocks(current_date)
        
        # 生成交易信号
        signals = []
        
        # 卖出不在选股列表中的持仓
        for data in self.datas:
            code = data._name
            pos = self.getposition(data)
            
            if pos.size > 0 and code not in selected_stocks:
                signals.append({
                    'code': code,
                    'action': 'SELL',
                    'size': pos.size
                })
        
        # 买入新选中的股票
        available_cash = self.get_cash()
        position_value = available_cash / max(len(selected_stocks), 1)
        
        for code in selected_stocks:
            # 查找对应的数据feed
            data = self.getdatabyname(code)
            if data is None:
                continue
            
            pos = self.getposition(data)
            if pos.size == 0:  # 没有持仓才买入
                size = int(position_value / data.close[0] / 100) * 100
                if size > 0:
                    signals.append({
                        'code': code,
                        'action': 'BUY',
                        'size': size
                    })
        
        self.last_rebalance_date = current_date
        
        return {
            'action': 'REBALANCE',
            'signals': signals,
            'selected_stocks': selected_stocks
        }
    
    def next(self):
        """策略主逻辑"""
        # 检查是否有未完成的订单
        if self.order:
            return
        
        # 生成信号
        signal = self.generate_signals()
        
        if not signal or signal.get('action') == 'HOLD':
            return
        
        # 执行调仓
        if signal['action'] == 'REBALANCE':
            for sig in signal.get('signals', []):
                code = sig['code']
                action = sig['action']
                size = sig['size']
                
                data = self.getdatabyname(code)
                if data is None:
                    continue
                
                if action == 'BUY':
                    self.order = self.buy(data=data, size=size)
                elif action == 'SELL':
                    self.order = self.sell(data=data, size=size)
    
    def get_factor_exposure(self) -> Dict[str, float]:
        """
        获取当前持仓的因子暴露
        
        Returns:
            各因子的平均暴露
        """
        current_date = self.datas[0].datetime.date(0)
        
        if current_date not in self.factor_data:
            return {}
        
        df = self.factor_data[current_date]
        
        # 获取持仓股票
        holdings = []
        for data in self.datas:
            pos = self.getposition(data)
            if pos.size > 0:
                holdings.append(data._name)
        
        if not holdings:
            return {}
        
        # 计算因子暴露
        exposure = {}
        for factor in self.params.factor_weights.keys():
            if factor in df.columns:
                exposure[factor] = df.loc[holdings, factor].mean()
        
        return exposure
    
    def get_attribution(self) -> Dict[str, Any]:
        """
        获取收益归因
        
        Returns:
            收益归因分析
        """
        # 这里简化实现，实际需要更复杂的归因分析
        exposure = self.get_factor_exposure()
        
        attribution = {
            'factor_exposure': exposure,
            'factor_contribution': {}
        }
        
        # 计算各因子的贡献（简化版）
        for factor, exp in exposure.items():
            weight = self.params.factor_weights.get(factor, 0)
            attribution['factor_contribution'][factor] = exp * weight
        
        return attribution

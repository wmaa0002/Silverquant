"""
多维度分析器 - 支持行业、市值分层分析
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import date

from database.db_manager import DatabaseManager


class MultiDimensionAnalyzer:
    """多维度回测分析器"""
    
    def __init__(self, run_id: str, db_manager: Optional[DatabaseManager] = None):
        """
        初始化
        
        Args:
            run_id: 回测运行ID
            db_manager: 数据库管理器
        """
        self.run_id = run_id
        self.db = db_manager or DatabaseManager()
        
        # 加载回测数据
        self.trades = None
        self.daily_pnl = None
        self.performance = None
        
        self._load_data()
    
    def _load_data(self):
        """加载回测数据"""
        result = self.db.get_backtest_result(self.run_id)
        self.trades = result.get('trades', pd.DataFrame())
        self.daily_pnl = result.get('daily_pnl', pd.DataFrame())
        self.performance = result.get('performance', pd.DataFrame())
    
    def analyze_by_industry(self) -> pd.DataFrame:
        """
        按行业分析
        
        Returns:
            行业分析结果DataFrame
        """
        if len(self.trades) == 0 or 'industry' not in self.trades.columns:
            return pd.DataFrame()
        
        analysis = self.trades.groupby('industry').agg({
            'amount': ['count', 'sum', 'mean'],
            'code': 'nunique'
        }).round(4)
        
        analysis.columns = ['trade_count', 'total_pnl', 'avg_pnl', 'stock_count']
        
        # 计算胜率
        win_rate = self.trades.groupby('industry').apply(
            lambda x: (x['amount'] > 0).sum() / len(x) if len(x) > 0 else 0
        ).round(4)
        analysis['win_rate'] = win_rate
        
        # 按总盈亏排序
        analysis = analysis.sort_values('total_pnl', ascending=False)
        
        return analysis
    
    def analyze_by_cap_group(self) -> pd.DataFrame:
        """
        按市值分组分析
        
        Returns:
            市值分组分析结果DataFrame
        """
        if len(self.trades) == 0 or 'market_cap_group' not in self.trades.columns:
            return pd.DataFrame()
        
        analysis = self.trades.groupby('market_cap_group').agg({
            'amount': ['count', 'sum', 'mean'],
            'code': 'nunique'
        }).round(4)
        
        analysis.columns = ['trade_count', 'total_pnl', 'avg_pnl', 'stock_count']
        
        # 计算胜率
        win_rate = self.trades.groupby('market_cap_group').apply(
            lambda x: (x['amount'] > 0).sum() / len(x) if len(x) > 0 else 0
        ).round(4)
        analysis['win_rate'] = win_rate
        
        # 按总盈亏排序
        analysis = analysis.sort_values('total_pnl', ascending=False)
        
        return analysis
    
    def analyze_by_time(self, freq: str = 'M') -> pd.DataFrame:
        """
        按时间维度分析
        
        Args:
            freq: 频率，'D'-日 'W'-周 'M'-月 'Y'-年
        
        Returns:
            时间维度分析结果DataFrame
        """
        if len(self.daily_pnl) == 0:
            return pd.DataFrame()
        
        df = self.daily_pnl.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        # 按频率聚合
        if freq == 'D':
            grouped = df
        elif freq == 'W':
            grouped = df.resample('W').agg({
                'daily_pnl': 'sum',
                'daily_return': 'sum',
                'total_value': 'last'
            })
        elif freq == 'M':
            grouped = df.resample('M').agg({
                'daily_pnl': 'sum',
                'daily_return': 'sum',
                'total_value': 'last'
            })
        elif freq == 'Y':
            grouped = df.resample('Y').agg({
                'daily_pnl': 'sum',
                'daily_return': 'sum',
                'total_value': 'last'
            })
        else:
            raise ValueError(f"不支持的频率: {freq}")
        
        # 计算累计收益
        grouped['cumulative_return'] = (1 + grouped['daily_return']).cumprod() - 1
        
        return grouped.round(4)
    
    def analyze_factor_exposure(self) -> pd.DataFrame:
        """
        分析因子暴露
        
        Returns:
            因子暴露分析结果
        """
        # 这里简化实现，实际需要从持仓数据中计算
        if len(self.trades) == 0:
            return pd.DataFrame()
        
        # 获取所有交易的股票和日期
        holdings = self.trades[['date', 'code']].drop_duplicates()
        
        # 获取因子数据
        factor_exposure = []
        
        for date_val in holdings['date'].unique():
            date_holdings = holdings[holdings['date'] == date_val]['code'].tolist()
            
            # 从数据库获取该日期的因子数据
            factor_df = self.db.get_factor_data(date_val)
            
            if len(factor_df) > 0:
                # 计算持仓的平均因子暴露
                holding_factors = factor_df[factor_df['code'].isin(date_holdings)]
                
                if len(holding_factors) > 0:
                    exposure = holding_factors.select_dtypes(include=[np.number]).mean()
                    exposure['date'] = date_val
                    factor_exposure.append(exposure)
        
        if factor_exposure:
            return pd.DataFrame(factor_exposure).set_index('date').round(4)
        
        return pd.DataFrame()
    
    def generate_report(self) -> Dict[str, pd.DataFrame]:
        """
        生成完整的多维度分析报告
        
        Returns:
            包含各维度分析结果的字典
        """
        report = {
            'industry_analysis': self.analyze_by_industry(),
            'cap_group_analysis': self.analyze_by_cap_group(),
            'monthly_analysis': self.analyze_by_time('M'),
            'factor_exposure': self.analyze_factor_exposure(),
        }
        
        return report
    
    def print_report(self):
        """打印多维度分析报告"""
        report = self.generate_report()
        
        print("\n" + "="*60)
        print("多维度回测分析报告")
        print("="*60)
        
        # 行业分析
        if len(report['industry_analysis']) > 0:
            print("\n【行业分析】")
            print(report['industry_analysis'].to_string())
        
        # 市值分组分析
        if len(report['cap_group_analysis']) > 0:
            print("\n【市值分组分析】")
            print(report['cap_group_analysis'].to_string())
        
        # 月度分析
        if len(report['monthly_analysis']) > 0:
            print("\n【月度收益分析】")
            print(report['monthly_analysis'].to_string())
        
        # 因子暴露
        if len(report['factor_exposure']) > 0:
            print("\n【因子暴露分析】")
            print(report['factor_exposure'].to_string())
        
        print("\n" + "="*60)


def analyze_backtest(run_id: str):
    """
    分析回测结果的便捷函数
    
    Args:
        run_id: 回测运行ID
    """
    analyzer = MultiDimensionAnalyzer(run_id)
    analyzer.print_report()

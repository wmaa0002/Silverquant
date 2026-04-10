"""
因子分析工具 - IC分析、因子收益率、因子相关性
"""
import pandas as pd
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from scipy import stats


class FactorAnalyzer:
    """因子分析器"""
    
    def __init__(self, factor_df: pd.DataFrame = None, returns_df: pd.DataFrame = None):
        """
        初始化
        
        Args:
            factor_df: 因子数据DataFrame，包含date, code, factor1, factor2...
            returns_df: 收益率数据DataFrame，包含date, code, return
        """
        self.factor_df = factor_df
        self.returns_df = returns_df
    
    def calculate_ic(
        self,
        factor_name: str,
        forward_period: int = 1,
        method: str = 'pearson'
    ) -> pd.DataFrame:
        """
        计算信息系数(IC)
        
        Args:
            factor_name: 因子名称
            forward_period: 前瞻期数（默认1天）
            method: 相关系数方法，'pearson'或'spearman'
        
        Returns:
            包含IC值的DataFrame
        """
        if self.factor_df is None or self.returns_df is None:
            raise ValueError("需要提供因子数据和收益率数据")
        
        # 合并数据
        merged = pd.merge(
            self.factor_df,
            self.returns_df,
            on=['date', 'code'],
            how='inner'
        )
        
        # 计算未来收益
        merged = merged.sort_values(['code', 'date'])
        merged['future_return'] = merged.groupby('code')['return'].shift(-forward_period)
        
        # 按日期计算IC
        ic_list = []
        
        for date, group in merged.groupby('date'):
            # 去除缺失值
            valid_data = group[[factor_name, 'future_return']].dropna()
            
            if len(valid_data) < 10:  # 样本太少跳过
                continue
            
            # 计算相关系数
            if method == 'pearson':
                ic, p_value = stats.pearsonr(
                    valid_data[factor_name],
                    valid_data['future_return']
                )
            else:  # spearman
                ic, p_value = stats.spearmanr(
                    valid_data[factor_name],
                    valid_data['future_return']
                )
            
            ic_list.append({
                'date': date,
                'ic': ic,
                'p_value': p_value,
                'sample_size': len(valid_data)
            })
        
        return pd.DataFrame(ic_list)
    
    def calculate_ic_stats(self, ic_df: pd.DataFrame) -> Dict[str, float]:
        """
        计算IC统计指标
        
        Args:
            ic_df: IC值DataFrame
        
        Returns:
            IC统计指标字典
        """
        if len(ic_df) == 0:
            return {}
        
        ic_series = ic_df['ic'].dropna()
        
        stats_dict = {
            'ic_mean': ic_series.mean(),
            'ic_std': ic_series.std(),
            'ic_ir': ic_series.mean() / ic_series.std() if ic_series.std() != 0 else 0,
            'ic_positive_ratio': (ic_series > 0).sum() / len(ic_series),
            'ic_positive_ratio_significant': (ic_series > 0.02).sum() / len(ic_series),
        }
        
        return stats_dict
    
    def calculate_quantile_returns(
        self,
        factor_name: str,
        n_quantiles: int = 5,
        forward_period: int = 1
    ) -> pd.DataFrame:
        """
        计算分位数收益
        
        Args:
            factor_name: 因子名称
            n_quantiles: 分位数数量（默认5分位）
            forward_period: 前瞻期数
        
        Returns:
            各分位数的收益DataFrame
        """
        if self.factor_df is None or self.returns_df is None:
            raise ValueError("需要提供因子数据和收益率数据")
        
        # 合并数据
        merged = pd.merge(
            self.factor_df,
            self.returns_df,
            on=['date', 'code'],
            how='inner'
        )
        
        # 计算未来收益
        merged = merged.sort_values(['code', 'date'])
        merged['future_return'] = merged.groupby('code')['return'].shift(-forward_period)
        merged = merged.dropna(subset=[factor_name, 'future_return'])
        
        # 按日期分档
        quantile_returns = []
        
        for date, group in merged.groupby('date'):
            if len(group) < n_quantiles * 10:  # 样本太少跳过
                continue
            
            # 分位数分组
            group['quantile'] = pd.qcut(
                group[factor_name],
                q=n_quantiles,
                labels=[f'Q{i+1}' for i in range(n_quantiles)],
                duplicates='drop'
            )
            
            # 计算每组的平均收益
            daily_return = group.groupby('quantile')['future_return'].mean()
            daily_return['date'] = date
            daily_return['long_short'] = daily_return.iloc[-1] - daily_return.iloc[0]
            
            quantile_returns.append(daily_return)
        
        result_df = pd.DataFrame(quantile_returns)
        if len(result_df) > 0:
            result_df = result_df.set_index('date')
        
        return result_df
    
    def calculate_factor_correlation(
        self,
        factor_names: List[str]
    ) -> pd.DataFrame:
        """
        计算因子相关性矩阵
        
        Args:
            factor_names: 因子名称列表
        
        Returns:
            相关性矩阵DataFrame
        """
        if self.factor_df is None:
            raise ValueError("需要提供因子数据")
        
        # 获取因子列
        available_factors = [f for f in factor_names if f in self.factor_df.columns]
        
        if len(available_factors) < 2:
            raise ValueError("至少需要两个有效的因子")
        
        # 计算相关性
        factor_corr = self.factor_df[available_factors].corr()
        
        return factor_corr
    
    def calculate_factor_turnover(
        self,
        factor_name: str,
        top_n: int = 50
    ) -> pd.DataFrame:
        """
        计算因子换手率
        
        Args:
            factor_name: 因子名称
            top_n: 选取的股票数量
        
        Returns:
            换手率DataFrame
        """
        if self.factor_df is None:
            raise ValueError("需要提供因子数据")
        
        turnover_list = []
        prev_stocks = set()
        
        for date, group in self.factor_df.groupby('date'):
            # 选取top N股票
            top_stocks = set(
                group.nlargest(top_n, factor_name)['code'].tolist()
            )
            
            # 计算换手率
            if prev_stocks:
                common = len(prev_stocks & top_stocks)
                turnover = 1 - common / top_n
            else:
                turnover = 1.0
            
            turnover_list.append({
                'date': date,
                'turnover': turnover,
                'stock_count': len(top_stocks)
            })
            
            prev_stocks = top_stocks
        
        return pd.DataFrame(turnover_list)
    
    def factor_autocorrelation(
        self,
        factor_name: str,
        lag: int = 1
    ) -> pd.DataFrame:
        """
        计算因子自相关性
        
        Args:
            factor_name: 因子名称
            lag: 滞后阶数
        
        Returns:
            自相关性DataFrame
        """
        if self.factor_df is None:
            raise ValueError("需要提供因子数据")
        
        autocorr_list = []
        
        for code, group in self.factor_df.groupby('code'):
            group = group.sort_values('date')
            
            if len(group) < lag + 10:
                continue
            
            # 计算自相关
            autocorr = group[factor_name].autocorr(lag=lag)
            
            autocorr_list.append({
                'code': code,
                'autocorr': autocorr
            })
        
        return pd.DataFrame(autocorr_list)
    
    def generate_factor_report(
        self,
        factor_names: List[str],
        forward_periods: List[int] = [1, 5, 10, 20]
    ) -> Dict[str, pd.DataFrame]:
        """
        生成因子分析报告
        
        Args:
            factor_names: 因子名称列表
            forward_periods: 前瞻期数列表
        
        Returns:
            包含各分析结果的字典
        """
        report = {}
        
        # IC分析
        ic_results = {}
        for factor in factor_names:
            for period in forward_periods:
                ic_df = self.calculate_ic(factor, period)
                ic_stats = self.calculate_ic_stats(ic_df)
                ic_results[f"{factor}_{period}d"] = ic_stats
        
        report['ic_analysis'] = pd.DataFrame(ic_results).T
        
        # 分位数收益
        quantile_results = {}
        for factor in factor_names:
            quantile_df = self.calculate_quantile_returns(factor, n_quantiles=5)
            if len(quantile_df) > 0:
                quantile_results[factor] = quantile_df.mean()
        
        if quantile_results:
            report['quantile_returns'] = pd.DataFrame(quantile_results).T
        
        # 因子相关性
        if len(factor_names) >= 2:
            report['factor_correlation'] = self.calculate_factor_correlation(factor_names)
        
        return report


def analyze_single_factor(
    factor_df: pd.DataFrame,
    returns_df: pd.DataFrame,
    factor_name: str
) -> Dict[str, Any]:
    """
    单因子分析的便捷函数
    
    Args:
        factor_df: 因子数据
        returns_df: 收益率数据
        factor_name: 因子名称
    
    Returns:
        分析结果字典
    """
    analyzer = FactorAnalyzer(factor_df, returns_df)
    
    # IC分析
    ic_df = analyzer.calculate_ic(factor_name)
    ic_stats = analyzer.calculate_ic_stats(ic_df)
    
    # 分位数收益
    quantile_df = analyzer.calculate_quantile_returns(factor_name)
    
    # 换手率
    turnover_df = analyzer.calculate_factor_turnover(factor_name)
    
    return {
        'ic_series': ic_df,
        'ic_stats': ic_stats,
        'quantile_returns': quantile_df,
        'turnover': turnover_df,
    }

"""
Tushare财务数据 fetcher

提供利润表、资产负债表、现金流量表的数据获取接口。

主要功能:
- TushareIncomeFetcher: 利润表数据获取
- TushareBalanceSheetFetcher: 资产负债表数据获取
- TushareCashFlowFetcher: 现金流量表数据获取

注意:
- 仅获取已报告的季度/年度数据（report_type='1'-'4'）
- 不获取TTM数据
"""

import logging
from typing import Optional, List, Dict, Any

import pandas as pd

from data.fetchers.tushare_adapter.base import TushareBaseFetcher

logger = logging.getLogger(__name__)


class TushareIncomeFetcher(TushareBaseFetcher):
    """
    利润表数据获取器
    
    获取上市公司利润表数据，支持:
    - 单股票获取
    - 日期范围批量获取
    - 仅获取已报告数据（不获取TTM）
    """
    
    # 利润表Tushare API字段到数据库字段的映射
    FIELD_MAPPING = {
        'ts_code': 'ts_code',
        'ann_date': 'ann_date',
        'f_ann_date': 'f_ann_date',
        'end_date': 'end_date',
        'report_type': 'report_type',
        'comp_type': 'comp_type',
        'basic_eps': 'basic_eps',
        'diluted_eps': 'diluted_eps',
        'total_revenue': 'total_revenue',
        'revenue': 'revenue',
        'total_profit': 'total_profit',
        'profit': 'profit',
        'income_tax': 'income_tax',
        'n_income': 'n_income',
        'n_income_attr_p': 'n_income_attr_p',
        'total_cogs': 'total_cogs',
        'operate_profit': 'operate_profit',
        'invest_income': 'invest_income',
        'non_op_income': 'non_op_income',
        'asset_impair_loss': 'asset_impair_loss',
        'net_profit_with_non_recurring': 'net_profit_with_non_recurring',
    }
    
    def fetch_by_stock(self, ts_code: str) -> pd.DataFrame:
        """
        获取单只股票的利润表数据
        
        Args:
            ts_code: 股票代码，格式为 '600000.SH' 或 '000001.SZ'
            
        Returns:
            包含利润表数据的DataFrame
        """
        logger.info(f"获取股票 {ts_code} 的利润表数据")
        
        try:
            # 获取所有季度和年度报表
            df = self._call_api(
                self.api.income,
                ts_code=ts_code,
                fields=list(self.FIELD_MAPPING.keys())
            )
            
            if df is None or df.empty:
                logger.warning(f"股票 {ts_code} 无利润表数据")
                return pd.DataFrame()
            
            # 仅保留已报告数据（report_type: 1-年报, 2-中期, 3-季报, 4-累积）
            df = df[df['report_type'].astype(str).isin(['1', '2', '3', '4'])]
            
            # 重命名字段以匹配数据库schema
            df = df.rename(columns=self.FIELD_MAPPING)
            
            # 添加数据来源
            df['data_source'] = 'tushare'
            
            logger.info(f"股票 {ts_code} 获取到 {len(df)} 条利润表记录")
            return df
            
        except Exception as e:
            logger.error(f"获取股票 {ts_code} 利润表数据失败: {e}")
            raise
    
    def fetch_all(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取日期范围内的所有股票利润表数据
        
        Args:
            start_date: 开始日期，格式 'YYYYMMDD'
            end_date: 结束日期，格式 'YYYYMMDD'
            
        Returns:
            包含所有利润表数据的DataFrame
        """
        logger.info(f"批量获取利润表数据: {start_date} ~ {end_date}")
        
        all_data = []
        
        try:
            # Tushare income API 支持日期范围查询
            df = self._call_api(
                self.api.income,
                start_date=start_date,
                end_date=end_date,
                fields=list(self.FIELD_MAPPING.keys())
            )
            
            if df is None or df.empty:
                logger.warning(f"日期范围内无利润表数据: {start_date} ~ {end_date}")
                return pd.DataFrame()
            
            # 仅保留已报告数据
            df = df[df['report_type'].astype(str).isin(['1', '2', '3', '4'])]
            
            # 重命名字段以匹配数据库schema
            df = df.rename(columns=self.FIELD_MAPPING)
            
            # 添加数据来源
            df['data_source'] = 'tushare'
            
            logger.info(f"批量获取到 {len(df)} 条利润表记录")
            return df
            
        except Exception as e:
            logger.error(f"批量获取利润表数据失败: {e}")
            raise


class TushareBalanceSheetFetcher(TushareBaseFetcher):
    """
    资产负债表数据获取器
    
    获取上市公司资产负债表数据，支持:
    - 单股票获取
    - 日期范围批量获取
    - 仅获取已报告数据（不获取TTM）
    """
    
    # 资产负债表Tushare API字段到数据库字段的映射
    FIELD_MAPPING = {
        'ts_code': 'ts_code',
        'ann_date': 'ann_date',
        'f_ann_date': 'f_ann_date',
        'end_date': 'end_date',
        'report_type': 'report_type',
        'comp_type': 'comp_type',
        'total_assets': 'total_assets',
        'total_liab': 'total_liab',
        'total_hldr_eqy_excl_min_int': 'total_hldr_eqy_excl_min_int',
        'hldr_eqy_excl_min_int': 'hldr_eqy_excl_min_int',
        'minority_int': 'minority_int',
        'total_liab_ht_holder': 'total_liab_ht_holder',
        'notes_payable': 'notes_payable',
        'accounts_payable': 'accounts_payable',
        'advance_receipts': 'advance_receipts',
        'total_current_assets': 'total_current_assets',
        'total_non_current_assets': 'total_non_current_assets',
        'fixed_assets': 'fixed_assets',
        'cip': 'cip',
        'total_current_liab': 'total_current_liab',
        'total_non_current_liab': 'total_non_current_liab',
        'lt_borrow': 'lt_borrow',
        'bonds_payable': 'bonds_payable',
    }
    
    def fetch_by_stock(self, ts_code: str) -> pd.DataFrame:
        """
        获取单只股票的资产负债表数据
        
        Args:
            ts_code: 股票代码，格式为 '600000.SH' 或 '000001.SZ'
            
        Returns:
            包含资产负债表数据的DataFrame
        """
        logger.info(f"获取股票 {ts_code} 的资产负债表数据")
        
        try:
            df = self._call_api(
                self.api.balancesheet,
                ts_code=ts_code,
                fields=list(self.FIELD_MAPPING.keys())
            )
            
            if df is None or df.empty:
                logger.warning(f"股票 {ts_code} 无资产负债表数据")
                return pd.DataFrame()
            
            # 仅保留已报告数据
            df = df[df['report_type'].astype(str).isin(['1', '2', '3', '4'])]
            
            # 重命名字段以匹配数据库schema
            df = df.rename(columns=self.FIELD_MAPPING)
            
            # 添加数据来源
            df['data_source'] = 'tushare'
            
            logger.info(f"股票 {ts_code} 获取到 {len(df)} 条资产负债表记录")
            return df
            
        except Exception as e:
            logger.error(f"获取股票 {ts_code} 资产负债表数据失败: {e}")
            raise
    
    def fetch_all(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取日期范围内的所有股票资产负债表数据
        
        Args:
            start_date: 开始日期，格式 'YYYYMMDD'
            end_date: 结束日期，格式 'YYYYMMDD'
            
        Returns:
            包含所有资产负债表数据的DataFrame
        """
        logger.info(f"批量获取资产负债表数据: {start_date} ~ {end_date}")
        
        try:
            df = self._call_api(
                self.api.balancesheet,
                start_date=start_date,
                end_date=end_date,
                fields=list(self.FIELD_MAPPING.keys())
            )
            
            if df is None or df.empty:
                logger.warning(f"日期范围内无资产负债表数据: {start_date} ~ {end_date}")
                return pd.DataFrame()
            
            # 仅保留已报告数据
            df = df[df['report_type'].astype(str).isin(['1', '2', '3', '4'])]
            
            # 重命名字段以匹配数据库schema
            df = df.rename(columns=self.FIELD_MAPPING)
            
            # 添加数据来源
            df['data_source'] = 'tushare'
            
            logger.info(f"批量获取到 {len(df)} 条资产负债表记录")
            return df
            
        except Exception as e:
            logger.error(f"批量获取资产负债表数据失败: {e}")
            raise


class TushareCashFlowFetcher(TushareBaseFetcher):
    """
    现金流量表数据获取器
    
    获取上市公司现金流量表数据，支持:
    - 单股票获取
    - 日期范围批量获取
    - 仅获取已报告数据（不获取TTM）
    """
    
    # 现金流量表Tushare API字段到数据库字段的映射
    FIELD_MAPPING = {
        'ts_code': 'ts_code',
        'ann_date': 'ann_date',
        'f_ann_date': 'f_ann_date',
        'end_date': 'end_date',
        'report_type': 'report_type',
        'comp_type': 'comp_type',
        'net_profit': 'net_profit',
        'fin_exp': 'fin_exp',
        'c_fr_oper_a': 'c_fr_oper_a',
        'c_fr_oper_a_op_ttp': 'c_fr_oper_a_op_ttp',
        'c_inf_fr_oper_a': 'c_inf_fr_oper_a',
        'c_paid_goods_sold': 'c_paid_goods_sold',
        'c_paid_to_for_employees': 'c_paid_to_for_employees',
        'c_paid_taxes': 'c_paid_taxes',
        'other_cash_fr_oper_a': 'other_cash_fr_oper_a',
        'n_cashflow_act': 'n_cashflow_act',
        'c_fr_oper_b': 'c_fr_oper_b',
        'c_fr_inv_a': 'c_fr_inv_a',
        'c_to_inv_a': 'c_to_inv_a',
        'c_fr_fin_a': 'c_fr_fin_a',
        'c_to_fin_a': 'c_to_fin_a',
        'n_cash_in_fin_a': 'n_cash_in_fin_a',
        'n_cash_in_op_b': 'n_cash_in_op_b',
        'n_cash_out_inv_b': 'n_cash_out_inv_b',
        'n_cash_out_fin_b': 'n_cash_out_fin_b',
        'n_cash_in_op_c': 'n_cash_in_op_c',
        'n_cash_out_inv_c': 'n_cash_out_inv_c',
        'n_cash_out_fin_c': 'n_cash_out_fin_c',
        'end_cash': 'end_cash',
        'cap_crisis_shrg': 'cap_crisis_shrg',
    }
    
    def fetch_by_stock(self, ts_code: str) -> pd.DataFrame:
        """
        获取单只股票的现金流量表数据
        
        Args:
            ts_code: 股票代码，格式为 '600000.SH' 或 '000001.SZ'
            
        Returns:
            包含现金流量表数据的DataFrame
        """
        logger.info(f"获取股票 {ts_code} 的现金流量表数据")
        
        try:
            df = self._call_api(
                self.api.cashflow,
                ts_code=ts_code,
                fields=list(self.FIELD_MAPPING.keys())
            )
            
            if df is None or df.empty:
                logger.warning(f"股票 {ts_code} 无现金流量表数据")
                return pd.DataFrame()
            
            # 仅保留已报告数据
            df = df[df['report_type'].astype(str).isin(['1', '2', '3', '4'])]
            
            # 重命名字段以匹配数据库schema
            df = df.rename(columns=self.FIELD_MAPPING)
            
            # 添加数据来源
            df['data_source'] = 'tushare'
            
            logger.info(f"股票 {ts_code} 获取到 {len(df)} 条现金流量表记录")
            return df
            
        except Exception as e:
            logger.error(f"获取股票 {ts_code} 现金流量表数据失败: {e}")
            raise
    
    def fetch_all(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取日期范围内的所有股票现金流量表数据
        
        Args:
            start_date: 开始日期，格式 'YYYYMMDD'
            end_date: 结束日期，格式 'YYYYMMDD'
            
        Returns:
            包含所有现金流量表数据的DataFrame
        """
        logger.info(f"批量获取现金流量表数据: {start_date} ~ {end_date}")
        
        try:
            df = self._call_api(
                self.api.cashflow,
                start_date=start_date,
                end_date=end_date,
                fields=list(self.FIELD_MAPPING.keys())
            )
            
            if df is None or df.empty:
                logger.warning(f"日期范围内无现金流量表数据: {start_date} ~ {end_date}")
                return pd.DataFrame()
            
            # 仅保留已报告数据
            df = df[df['report_type'].astype(str).isin(['1', '2', '3', '4'])]
            
            # 重命名字段以匹配数据库schema
            df = df.rename(columns=self.FIELD_MAPPING)
            
            # 添加数据来源
            df['data_source'] = 'tushare'
            
            logger.info(f"批量获取到 {len(df)} 条现金流量表记录")
            return df
            
        except Exception as e:
            logger.error(f"批量获取现金流量表数据失败: {e}")
            raise
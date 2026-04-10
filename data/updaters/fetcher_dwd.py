"""
Tushare统一数据更新器 - DWD层数据仓库

集成所有Tushare适配器，提供一站式数据更新功能：
- 日线数据 (dwd_daily_price)
- 每日指标 (dwd_daily_basic)
- 复权因子 (dwd_adj_factor)
- 利润表 (dwd_income)
- 资产负债表 (dwd_balancesheet)
- 现金流量表 (dwd_cashflow)
- 指数日线 (dwd_index_daily)
- 股票信息 (dwd_stock_info)
- 交易日历 (dwd_trade_calendar)

支持模式:
- --full: 全量更新，从start_date开始
- --incremental: 增量更新，基于dwd_trade_calendar自动判断
- --date: 更新指定日期数据

API限制: Tushare标准版50次/分钟
"""
import sys
import os
from multiprocessing import Pool, cpu_count
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import argparse
import time
import logging

import pandas as pd
import duckdb
from tqdm import tqdm

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from data.fetchers.tushare_adapter import (
    TushareBaseFetcher,
    TushareDailyPriceFetcher,
    TushareDailyBasicFetcher,
    TushareAdjFactorFetcher,
    TushareIncomeFetcher,
    TushareBalanceSheetFetcher,
    TushareCashFlowFetcher,
    TushareIndexFetcher,
    TushareTradeCalFetcher,
)
from data.fetchers.baostock_adapter import (
    BaostockDailyPriceFetcher,
    BaostockStockInfoFetcher,
)
from data.fetchers.baostock_adapter.code_converter import to_tushare
from data.fetchers.rate_limiter import tushare_limiter
from database.schema import (
    CREATE_DWD_DAILY_PRICE_TABLE,
    CREATE_DWD_DAILY_BASIC_TABLE,
    CREATE_DWD_ADJ_FACTOR_TABLE,
    CREATE_DWD_INCOME_TABLE,
    CREATE_DWD_BALANCESHEET_TABLE,
    CREATE_DWD_CASHFLOW_TABLE,
    CREATE_DWD_INDEX_DAILY_TABLE,
    CREATE_DWD_STOCK_INFO_TABLE,
    CREATE_DWD_TRADE_CALENDAR_TABLE,
)

DB_PATH = os.path.join(project_root, 'data', 'Astock3.duckdb')

from scripts.log_utils import setup_logger
logger = setup_logger('fetcher_dwd', 'pipeline')


def _process_stock_financial(code: str) -> Dict[str, Any]:
    """模块级worker函数: 处理单只股票的财务数据"""
    ts_code = to_tushare(code)
    income_fetcher = TushareIncomeFetcher()
    balancesheet_fetcher = TushareBalanceSheetFetcher()
    cashflow_fetcher = TushareCashFlowFetcher()
    
    income_result = income_fetcher.fetch_by_stock(ts_code)
    bs_result = balancesheet_fetcher.fetch_by_stock(ts_code)
    cf_result = cashflow_fetcher.fetch_by_stock(ts_code)
    
    return {
        'code': code,
        'income': {'records': len(income_result) if income_result is not None and not income_result.empty else 0},
        'balancesheet': {'records': len(bs_result) if bs_result is not None and not bs_result.empty else 0},
        'cashflow': {'records': len(cf_result) if cf_result is not None and not cf_result.empty else 0}
    }


class DWDFetcher:
    """
    Tushare统一数据更新器
    
    集成所有Tushare适配器，提供DWD层数据仓库的一站式更新能力。
    
    使用示例:
        fetcher = DWDFetcher()
        
        # 更新单日日线数据
        fetcher.update_daily('20260403', '20260403')
        
        # 增量更新
        fetcher.update_incremental()
        
        # 全量更新日线数据
        fetcher.update_daily('20260101', '20260406')
    """
    
    # 默认指数列表
    DEFAULT_INDICES = [
        '000001.SH',  # 上证指数
        '399001.SZ',  # 深证成指
        '399006.SZ',  # 创业板指
        '000300.SH',  # 沪深300
        '000016.SH',  # 上证50
        '000905.SH',  # 中证500
        '000852.SH',  # 中证1000
    ]
    
    def __init__(self, db_path: str = DB_PATH, source: str = 'tushare'):
        """
        初始化DWDFetcher
        
        Args:
            db_path: DuckDB数据库路径
            source: 数据源 ('tushare' 或 'baostock')
        """
        self.db_path = db_path
        self.source = source
        self._ensure_tables()
        
        # 根据source初始化对应的日线fetcher
        if source == 'tushare':
            self.daily_fetcher = TushareDailyPriceFetcher()
        elif source == 'baostock':
            self.daily_fetcher = BaostockDailyPriceFetcher()
        
        # 初始化所有Tushare适配器 (财务数据等仍使用Tushare)
        self.daily_basic_fetcher = TushareDailyBasicFetcher()
        self.adj_factor_fetcher = TushareAdjFactorFetcher()
        self.income_fetcher = TushareIncomeFetcher()
        self.balancesheet_fetcher = TushareBalanceSheetFetcher()
        self.cashflow_fetcher = TushareCashFlowFetcher()
        self.index_fetcher = TushareIndexFetcher()
        self.trade_cal_fetcher = TushareTradeCalFetcher()
        
        logger.info(f"DWDFetcher初始化完成, source={source}")
    
    def _ensure_tables(self) -> None:
        """确保所有DWD表存在"""
        db = duckdb.connect(self.db_path)
        try:
            db.execute(CREATE_DWD_DAILY_PRICE_TABLE)
            db.execute(CREATE_DWD_DAILY_BASIC_TABLE)
            db.execute(CREATE_DWD_ADJ_FACTOR_TABLE)
            db.execute(CREATE_DWD_INCOME_TABLE)
            db.execute(CREATE_DWD_BALANCESHEET_TABLE)
            db.execute(CREATE_DWD_CASHFLOW_TABLE)
            db.execute(CREATE_DWD_INDEX_DAILY_TABLE)
            db.execute(CREATE_DWD_STOCK_INFO_TABLE)
            db.execute(CREATE_DWD_TRADE_CALENDAR_TABLE)
            logger.info("DWD表检查完成")
        finally:
            db.close()
    
    def _get_stock_list_from_db(self) -> List[str]:
        """从数据库获取股票列表（从 dwd_stock_info 读取）"""
        db = duckdb.connect(self.db_path)
        try:
            # dwd_stock_info.symbol = 股票代码如 600000
            # 已退市的股票 list_status='D'，只返回在市股票
            result = db.execute(
                "SELECT symbol FROM dwd_stock_info WHERE list_status = 'L' ORDER BY symbol"
            ).fetchall()
            return [row[0] for row in result]
        finally:
            db.close()
    
    def _get_latest_date(self, table: str, date_col: str = 'trade_date') -> Optional[datetime]:
        """获取表中最新日期"""
        db = duckdb.connect(self.db_path)
        try:
            result = db.execute(f"SELECT MAX({date_col}) FROM {table}").fetchone()
            if result and result[0]:
                return pd.to_datetime(result[0]).date()
            return None
        except Exception as e:
            logger.warning(f"查询最新日期失败: {e}")
            return None
        finally:
            db.close()
    
    def get_latest_trade_date(self, table_name: str) -> Optional[str]:
        """
        获取指定DWD表的最新交易日期
        
        Args:
            table_name: DWD表名 (dwd_daily_price, dwd_daily_basic, dwd_index_daily等)
            
        Returns:
            最新交易日期字符串 YYYYMMDD，如果没有数据返回None
        """
        db = duckdb.connect(self.db_path)
        try:
            # 确定日期列名
            date_col = 'trade_date' if table_name != 'dwd_stock_info' else 'list_date'
            result = db.execute(f"SELECT MAX({date_col}) FROM {table_name}").fetchone()
            if result and result[0]:
                date_val = pd.to_datetime(result[0]).strftime('%Y%m%d')
                logger.info(f"{table_name} 最新日期: {date_val}")
                return date_val
            return None
        except Exception as e:
            logger.warning(f"查询{table_name}最新日期失败: {e}")
            return None
        finally:
            db.close()
    
    def get_next_trade_date(self, from_date: str) -> Optional[str]:
        """
        从dwd_trade_calendar获取from_date之后的下一个交易日
        
        Args:
            from_date: 参考日期 YYYYMMDD
            
        Returns:
            下一个交易日期字符串 YYYYMMDD，如果没有找到返回None
        """
        db = duckdb.connect(self.db_path)
        try:
            # 将YYYYMMDD转换为YYYY-MM-DD格式进行查询
            from_date_formatted = f"{from_date[:4]}-{from_date[4:6]}-{from_date[6:8]}"
            result = db.execute("""
                SELECT MIN(trade_date) FROM dwd_trade_calendar 
                WHERE is_open = TRUE AND trade_date > ?
            """, [from_date_formatted]).fetchone()
            
            if result and result[0]:
                next_date = pd.to_datetime(result[0]).strftime('%Y%m%d')
                logger.info(f"下一个交易日: {next_date}")
                return next_date
            return None
        except Exception as e:
            logger.warning(f"查询下一个交易日失败: {e}")
            return None
        finally:
            db.close()
    
    def _get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表"""
        df = self.trade_cal_fetcher.fetch(start_date=start_date, end_date=end_date, exchange='SSE')
        if df is None or df.empty:
            return []
        trade_dates = df[df['is_open'] == 1]['trade_date'].tolist()
        return [d.replace('-', '') for d in trade_dates]
    
    def _save_to_db(self, df: pd.DataFrame, table: str) -> int:
        """
        保存数据到数据库，使用INSERT OR REPLACE
        
        Args:
            df: 数据DataFrame
            table: 表名
            
        Returns:
            保存的记录数
        """
        if df is None or df.empty:
            return 0
        
        df = df.copy()
        
        # 转换日期格式
        date_cols = ['trade_date', 'ann_date', 'f_ann_date', 'end_date', 'list_date', 'listing_date', 'delist_date']
        for col in date_cols:
            if col in df.columns:
                # 空字符串转为NULL
                df[col] = df[col].replace('', pd.NA)
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # 处理数据类型 - 日期列不需要转数字
        skip_cols = ['ts_code', 'index_code', 'symbol', 'name', 'area', 'industry', 
                     'market', 'is_hs', 'act_name', 'exchange', 'report_type', 
                     'comp_type', 'data_source', 'list_status', 'delist_date']
        date_cols = ['trade_date', 'ann_date', 'f_ann_date', 'end_date', 'list_date']
        numeric_skip = skip_cols + date_cols
        for col in df.columns:
            if col not in numeric_skip and str(df[col].dtype) == 'object':
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        db = duckdb.connect(self.db_path)
        try:
            db.execute("CREATE TEMPORARY TABLE temp_data AS SELECT * FROM df")
            cols = ', '.join(df.columns)
            db.execute(f"INSERT OR REPLACE INTO {table} ({cols}) SELECT {cols} FROM temp_data")
            db.execute("DROP TABLE temp_data")
            return len(df)
        finally:
            db.close()
    
    def update_daily(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        更新日线数据 (dwd_daily_price)
        
        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            
        Returns:
            更新统计信息
        """
        logger.info(f"开始更新日线数据: {start_date} ~ {end_date}")
        start_time = time.time()
        
        trade_dates = self._get_trade_dates(start_date, end_date)
        if not trade_dates:
            logger.warning(f"未获取到交易日: {start_date} ~ {end_date}")
            return {'success': 0, 'fail': 0, 'records': 0, 'elapsed': 0}
        
        success_count = 0
        fail_count = 0
        total_records = 0
        
        for i, trade_date in enumerate(trade_dates):
            try:
                df = self.daily_fetcher.fetch_by_date(trade_date)
                if df is not None and not df.empty:
                    records = self._save_to_db(df, 'dwd_daily_price')
                    total_records += records
                    success_count += 1
                else:
                    fail_count += 1
                
                if (i + 1) % 10 == 0:
                    logger.info(f"日线更新进度: {i+1}/{len(trade_dates)}")
                    
            except Exception as e:
                logger.error(f"更新日线失败 {trade_date}: {e}")
                fail_count += 1
        
        elapsed = time.time() - start_time
        logger.info(f"日线数据更新完成: 成功{success_count}天, 失败{fail_count}天, 记录{total_records}条, 耗时{elapsed:.1f}秒")
        
        return {
            'success': success_count,
            'fail': fail_count,
            'records': total_records,
            'elapsed': elapsed
        }
    
    def update_daily_parallel(self, start_date: str, end_date: str, num_workers: int = 4) -> Dict[str, Any]:
        """
        并行更新日线数据 (dwd_daily_price)
        
        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            num_workers: 并行进程数，默认4
        
        Returns:
            更新统计信息
        """
        logger.info(f"开始并行更新日线数据: {start_date} ~ {end_date}, 进程数: {num_workers}")
        start_time = time.time()
        
        trade_dates = self._get_trade_dates(start_date, end_date)
        if not trade_dates:
            logger.warning(f"未获取到交易日: {start_date} ~ {end_date}")
            return {'success': 0, 'fail': 0, 'records': 0, 'elapsed': 0}
        
        total_dates = len(trade_dates)
        logger.info(f"获取到 {total_dates} 个交易日")
        
        # Worker函数 - 获取单日数据
        def fetch_single_date(trade_date: str) -> Dict[str, Any]:
            """Worker函数: 获取单日日线数据"""
            try:
                df = self.daily_fetcher.fetch_by_date(trade_date)
                if df is not None and not df.empty:
                    return {'success': 1, 'fail': 0, 'records': len(df), 'df': df, 'date': trade_date}
                return {'success': 0, 'fail': 1, 'records': 0, 'df': None, 'date': trade_date}
            except Exception as e:
                logger.error(f"获取日线失败 {trade_date}: {e}")
                return {'success': 0, 'fail': 1, 'records': 0, 'df': None, 'date': trade_date}
        
        # 限制worker数量，避免超过Tushare限制 (50次/分钟)
        effective_workers = min(num_workers, 4)
        logger.info(f"使用 {effective_workers} 个并行进程")
        
        all_dfs = []
        success_count = 0
        fail_count = 0
        total_records = 0
        
        # 使用进程池并行获取
        with Pool(processes=effective_workers) as pool:
            results = list(tqdm(
                pool.imap(fetch_single_date, trade_dates),
                total=total_dates,
                desc="并行更新日线",
                unit="天"
            ))
        
        # 汇总结果
        for result in results:
            if result['success']:
                success_count += 1
                total_records += result['records']
                if result['df'] is not None:
                    all_dfs.append(result['df'])
            else:
                fail_count += 1
        
        # 批量写入数据库
        if all_dfs:
            logger.info(f"准备写入 {len(all_dfs)} 个DataFrame到数据库...")
            combined_df = pd.concat(all_dfs, ignore_index=True)
            self._save_to_db(combined_df, 'dwd_daily_price')
        
        elapsed = time.time() - start_time
        logger.info(f"并行日线数据更新完成: 成功{success_count}天, 失败{fail_count}天, 记录{total_records}条, 耗时{elapsed:.1f}秒")
        
        return {
            'success': success_count,
            'fail': fail_count,
            'records': total_records,
            'elapsed': elapsed
        }
    
    def update_daily_by_stock(self, start_date: str, end_date: str, num_workers: int = 4) -> Dict[str, Any]:
        """
        使用baostock按股票下载模式更新日线数据
        
        baostock需要按股票下载，每个股票调用一次query_history_k_data_plus
        因此使用多进程并行加速
        
        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            num_workers: 并行进程数
        
        Returns:
            更新统计信息
        """
        if self.source != 'baostock':
            logger.error("update_daily_by_stock仅支持baostock数据源")
            return {'success': 0, 'fail': 0, 'records': 0, 'elapsed': 0}
        
        logger.info(f"开始按股票更新日线数据(baostock): {start_date} ~ {end_date}, 进程数: {num_workers}")
        start_time = time.time()
        
        stock_list = self._get_stock_list_from_db()
        if not stock_list:
            logger.warning("股票列表为空")
            return {'success': 0, 'fail': 0, 'records': 0, 'elapsed': 0}
        
        total_stocks = len(stock_list)
        logger.info(f"共 {total_stocks} 只股票")
        
        def fetch_single_stock(code: str) -> Dict[str, Any]:
            """Worker函数: 获取单只股票日线数据"""
            try:
                df = self.daily_fetcher.fetch_by_code(code, start_date, end_date)
                if df is not None and not df.empty:
                    return {'success': 1, 'fail': 0, 'records': len(df), 'df': df, 'code': code}
                return {'success': 0, 'fail': 1, 'records': 0, 'df': None, 'code': code}
            except Exception as e:
                logger.error(f"获取日线失败 {code}: {e}")
                return {'success': 0, 'fail': 1, 'records': 0, 'df': None, 'code': code}
        
        effective_workers = min(num_workers, cpu_count() - 1 or 1)
        logger.info(f"使用 {effective_workers} 个并行进程")
        
        all_dfs = []
        success_count = 0
        fail_count = 0
        total_records = 0
        
        with Pool(processes=effective_workers) as pool:
            results = list(tqdm(
                pool.imap(fetch_single_stock, stock_list),
                total=total_stocks,
                desc="按股票更新日线",
                unit="股"
            ))
        
        for result in results:
            if result['success']:
                success_count += 1
                total_records += result['records']
                if result['df'] is not None:
                    all_dfs.append(result['df'])
            else:
                fail_count += 1
        
        if all_dfs:
            logger.info(f"准备写入 {len(all_dfs)} 个DataFrame到数据库...")
            combined_df = pd.concat(all_dfs, ignore_index=True)
            self._save_to_db(combined_df, 'dwd_daily_price')
        
        elapsed = time.time() - start_time
        logger.info(f"按股票更新日线完成: 成功{success_count}只, 失败{fail_count}只, 记录{total_records}条, 耗时{elapsed:.1f}秒")
        
        return {
            'success': success_count,
            'fail': fail_count,
            'records': total_records,
            'elapsed': elapsed
        }
    
    def update_daily_basic(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        更新每日指标数据 (dwd_daily_basic)
        
        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            
        Returns:
            更新统计信息
        """
        logger.info(f"开始更新每日指标: {start_date} ~ {end_date}")
        start_time = time.time()
        
        trade_dates = self._get_trade_dates(start_date, end_date)
        if not trade_dates:
            logger.warning(f"未获取到交易日: {start_date} ~ {end_date}")
            return {'success': 0, 'fail': 0, 'records': 0, 'elapsed': 0}
        
        success_count = 0
        fail_count = 0
        total_records = 0
        
        for i, trade_date in enumerate(trade_dates):
            try:
                df = self.daily_basic_fetcher.fetch_by_date(trade_date)
                if df is not None and not df.empty:
                    records = self._save_to_db(df, 'dwd_daily_basic')
                    total_records += records
                    success_count += 1
                else:
                    fail_count += 1
                
                if (i + 1) % 10 == 0:
                    logger.info(f"每日指标更新进度: {i+1}/{len(trade_dates)}")
                    
            except Exception as e:
                logger.error(f"更新每日指标失败 {trade_date}: {e}")
                fail_count += 1
        
        elapsed = time.time() - start_time
        logger.info(f"每日指标更新完成: 成功{success_count}天, 失败{fail_count}天, 记录{total_records}条, 耗时{elapsed:.1f}秒")
        
        return {
            'success': success_count,
            'fail': fail_count,
            'records': total_records,
            'elapsed': elapsed
        }
    
    def update_adj_factor(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        更新复权因子 (dwd_adj_factor)
        
        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            
        Returns:
            更新统计信息
        """
        logger.info(f"开始更新复权因子: {start_date} ~ {end_date}")
        start_time = time.time()
        
        stock_list = self._get_stock_list_from_db()
        success_count = 0
        fail_count = 0
        total_records = 0
        
        for i, code in enumerate(stock_list):
            try:
                ts_code = to_tushare(code)
                df = self.adj_factor_fetcher.fetch(ts_code, start_date, end_date)
                if df is not None and not df.empty:
                    records = self._save_to_db(df, 'dwd_adj_factor')
                    total_records += records
                    success_count += 1
                else:
                    fail_count += 1
                
                if (i + 1) % 100 == 0:
                    logger.info(f"复权因子更新进度: {i+1}/{len(stock_list)}")
                    
            except Exception as e:
                logger.error(f"更新复权因子失败 {code}: {e}")
                fail_count += 1
        
        elapsed = time.time() - start_time
        logger.info(f"复权因子更新完成: 成功{success_count}只, 失败{fail_count}只, 记录{total_records}条, 耗时{elapsed:.1f}秒")
        
        return {
            'success': success_count,
            'fail': fail_count,
            'records': total_records,
            'elapsed': elapsed
        }
    
    def update_income(self, ts_code: str) -> Dict[str, Any]:
        """
        更新利润表数据 (dwd_income)
        
        Args:
            ts_code: 股票代码，如 '600000.SH'
            
        Returns:
            更新统计信息
        """
        logger.info(f"开始更新利润表: {ts_code}")
        start_time = time.time()
        
        try:
            df = self.income_fetcher.fetch_by_stock(ts_code)
            if df is not None and not df.empty:
                records = self._save_to_db(df, 'dwd_income')
                elapsed = time.time() - start_time
                logger.info(f"利润表更新完成: {ts_code}, 记录{records}条, 耗时{elapsed:.1f}秒")
                return {'success': 1, 'fail': 0, 'records': records, 'elapsed': elapsed}
            else:
                logger.warning(f"利润表无数据: {ts_code}")
                return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
        except Exception as e:
            logger.error(f"更新利润表失败 {ts_code}: {e}")
            return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
    
    def update_balancesheet(self, ts_code: str) -> Dict[str, Any]:
        """
        更新资产负债表 (dwd_balancesheet)
        
        Args:
            ts_code: 股票代码，如 '600000.SH'
            
        Returns:
            更新统计信息
        """
        logger.info(f"开始更新资产负债表: {ts_code}")
        start_time = time.time()
        
        try:
            df = self.balancesheet_fetcher.fetch_by_stock(ts_code)
            if df is not None and not df.empty:
                records = self._save_to_db(df, 'dwd_balancesheet')
                elapsed = time.time() - start_time
                logger.info(f"资产负债表更新完成: {ts_code}, 记录{records}条, 耗时{elapsed:.1f}秒")
                return {'success': 1, 'fail': 0, 'records': records, 'elapsed': elapsed}
            else:
                logger.warning(f"资产负债表无数据: {ts_code}")
                return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
        except Exception as e:
            logger.error(f"更新资产负债表失败 {ts_code}: {e}")
            return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
    
    def update_cashflow(self, ts_code: str) -> Dict[str, Any]:
        """
        更新现金流量表 (dwd_cashflow)
        
        Args:
            ts_code: 股票代码，如 '600000.SH'
            
        Returns:
            更新统计信息
        """
        logger.info(f"开始更新现金流量表: {ts_code}")
        start_time = time.time()
        
        try:
            df = self.cashflow_fetcher.fetch_by_stock(ts_code)
            if df is not None and not df.empty:
                records = self._save_to_db(df, 'dwd_cashflow')
                elapsed = time.time() - start_time
                logger.info(f"现金流量表更新完成: {ts_code}, 记录{records}条, 耗时{elapsed:.1f}秒")
                return {'success': 1, 'fail': 0, 'records': records, 'elapsed': elapsed}
            else:
                logger.warning(f"现金流量表无数据: {ts_code}")
                return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
        except Exception as e:
            logger.error(f"更新现金流量表失败 {ts_code}: {e}")
            return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
    
    def update_index(self, index_code: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        更新指数日线数据 (dwd_index_daily)
        
        Args:
            index_code: 指数代码，如 '000001.SH'
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            
        Returns:
            更新统计信息
        """
        logger.info(f"开始更新指数日线: {index_code} {start_date} ~ {end_date}")
        start_time = time.time()
        
        try:
            df = self.index_fetcher.fetch(index_code, start_date, end_date)
            if df is not None and not df.empty:
                records = self._save_to_db(df, 'dwd_index_daily')
                elapsed = time.time() - start_time
                logger.info(f"指数日线更新完成: {index_code}, 记录{records}条, 耗时{elapsed:.1f}秒")
                return {'success': 1, 'fail': 0, 'records': records, 'elapsed': elapsed}
            else:
                logger.warning(f"指数日线无数据: {index_code}")
                return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
        except Exception as e:
            logger.error(f"更新指数日线失败 {index_code}: {e}")
            return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
    
    def update_stock_info(self, source: Optional[str] = None) -> Dict[str, Any]:
        """
        更新股票信息 (dwd_stock_info)
        
        Args:
            source: 数据源 ('tushare' 或 'baostock')，默认使用 self.source
            
        Returns:
            更新统计信息
        """
        if source is None:
            source = self.source
        
        logger.info(f"开始更新股票信息, 数据源: {source}")
        
        if source == 'baostock':
            return self._update_stock_info_baostock()
        else:
            return self._update_stock_info_tushare()

    def _update_stock_info_baostock(self) -> Dict[str, Any]:
        """使用 baostock 更新股票信息"""
        from data.fetchers.baostock_adapter import BaostockStockInfoFetcher
        
        start_time = time.time()
        
        try:
            fetcher = BaostockStockInfoFetcher()
            df = fetcher.fetch_all()
            
            if df is None or df.empty:
                logger.warning("Baostock 股票信息无数据")
                return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
            
            # BaostockStockInfoFetcher 已做好所有字段映射:
            # ts_code, symbol, name, area, industry, market, listing_date, 
            # is_hs, act_name, list_status, delist_date, data_source
            
            # 重命名 listing_date -> list_date (兼容表结构)
            df = df.rename(columns={'listing_date': 'list_date'})
            
            # 确保 data_source 正确
            df['data_source'] = 'baostock'
            
            records = self._save_to_db(df, 'dwd_stock_info')
            elapsed = time.time() - start_time
            
            logger.info(f"股票信息更新完成 (baostock): {records}条, 耗时{elapsed:.1f}秒")
            return {'success': 1, 'fail': 0, 'records': records, 'elapsed': elapsed}
            
        except Exception as e:
            logger.error(f"更新股票信息失败 (baostock): {e}")
            return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}

    def _update_stock_info_tushare(self) -> Dict[str, Any]:
        """使用 tushare 更新股票信息"""
        start_time = time.time()
        
        try:
            from data.fetchers.tushare_adapter.base import TushareBaseFetcher
            base = TushareBaseFetcher()
            
            if not base._ensure_api():
                logger.error("Tushare API未初始化")
                return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
            
            tushare_limiter.wait_if_needed()
            df = base.api.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,market,list_date,is_hs,act_name,list_status')
            
            if df is not None and not df.empty:
                df['data_source'] = 'tushare'
                records = self._save_to_db(df, 'dwd_stock_info')
                elapsed = time.time() - start_time
                logger.info(f"股票信息更新完成 (tushare): 记录{records}条, 耗时{elapsed:.1f}秒")
                return {'success': 1, 'fail': 0, 'records': records, 'elapsed': elapsed}
            else:
                logger.warning("股票信息无数据")
                return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
        except Exception as e:
            logger.error(f"更新股票信息失败 (tushare): {e}")
            return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
    
    def update_trade_calendar(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        更新交易日历 (dwd_trade_calendar)
        
        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            
        Returns:
            更新统计信息
        """
        logger.info(f"开始更新交易日历: {start_date} ~ {end_date}")
        start_time = time.time()
        
        try:
            df = self.trade_cal_fetcher.fetch(start_date, end_date)
            if df is not None and not df.empty:
                # 转换is_open为布尔值
                if 'is_open' in df.columns:
                    df['is_open'] = df['is_open'].astype(str).str.lower() == 'true'
                records = self._save_to_db(df, 'dwd_trade_calendar')
                elapsed = time.time() - start_time
                logger.info(f"交易日历更新完成: 记录{records}条, 耗时{elapsed:.1f}秒")
                return {'success': 1, 'fail': 0, 'records': records, 'elapsed': elapsed}
            else:
                logger.warning("交易日历无数据")
                return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
        except Exception as e:
            logger.error(f"更新交易日历失败: {e}")
            return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
    
    def update_incremental(self, data_type: str = 'daily') -> Dict[str, Any]:
        """
        增量更新 - 基于目标表的最新日期和dwd_trade_calendar自动判断需要更新的日期
        
        Args:
            data_type: 数据类型 (daily, daily_basic, index)
            
        Returns:
            更新统计信息
        """
        logger.info(f"开始增量更新: {data_type}")
        
        # 数据类型到表名的映射
        table_mapping = {
            'daily': 'dwd_daily_price',
            'daily_basic': 'dwd_daily_basic',
            'index': 'dwd_index_daily',
        }
        
        if data_type not in table_mapping:
            logger.error(f"不支持的数据类型: {data_type}")
            return {'success': 0, 'fail': 0, 'records': 0, 'elapsed': 0}
        
        table_name = table_mapping[data_type]
        
        # 获取目标表的最新日期
        latest_date = self.get_latest_trade_date(table_name)
        if latest_date is None:
            logger.warning(f"{table_name}为空，使用默认起始日期 20260101")
            start_date = '20260101'
        else:
            # 获取该日期之后的下一个交易日
            next_date = self.get_next_trade_date(latest_date)
            if next_date is None:
                logger.info(f"{table_name}已是最新的，无需更新")
                return {'success': 0, 'fail': 0, 'records': 0, 'elapsed': 0}
            start_date = next_date
        
        end_date = datetime.now().strftime('%Y%m%d')
        
        logger.info(f"增量更新范围: {start_date} ~ {end_date}")
        
        if data_type == 'daily':
            return self.update_daily(start_date, end_date)
        elif data_type == 'daily_basic':
            return self.update_daily_basic(start_date, end_date)
        elif data_type == 'index':
            return self.update_index(self.DEFAULT_INDICES[0], start_date, end_date)
        else:
            logger.error(f"不支持的数据类型: {data_type}")
            return {'success': 0, 'fail': 0, 'records': 0, 'elapsed': 0}
    
    def update_financial_multiprocess(self, num_workers: int = 4) -> Dict[str, Any]:
        """
        多进程更新财务数据 (income, balancesheet, cashflow)
        
        Args:
            num_workers: 并行进程数
            
        Returns:
            更新统计信息
        """
        logger.info(f"开始多进程更新财务数据, 进程数: {num_workers}")
        start_time = time.time()
        
        stock_list = self._get_stock_list_from_db()
        total = len(stock_list)
        
        effective_workers = min(num_workers, cpu_count() - 1 or 1)
        logger.info(f"使用 {effective_workers} 个并行进程处理 {total} 只股票")
        
        results = []
        with Pool(processes=effective_workers) as pool:
            for result in tqdm(pool.imap(_process_stock_financial, stock_list), 
                               total=total, desc="财务数据更新", unit="股"):
                results.append(result)
        
        elapsed = time.time() - start_time
        
        total_income = sum(r['income']['records'] for r in results)
        total_bs = sum(r['balancesheet']['records'] for r in results)
        total_cf = sum(r['cashflow']['records'] for r in results)
        
        logger.info(f"财务数据更新完成: 利润表{total_income}条, 资产负债表{total_bs}条, 现金流量表{total_cf}条, 耗时{elapsed:.1f}秒")
        
        return {
            'income_records': total_income,
            'balancesheet_records': total_bs,
            'cashflow_records': total_cf,
            'elapsed': elapsed
        }


def run_cli():
    """CLI入口"""
    parser = argparse.ArgumentParser(description='Tushare统一数据更新器 - DWD层')
    
    # 更新模式
    parser.add_argument('--full', action='store_true', help='全量更新模式')
    parser.add_argument('--incremental', action='store_true', help='增量更新模式')
    parser.add_argument('--date', type=str, help='更新指定日期 YYYYMMDD')
    
    # 数据类型
    parser.add_argument('--data-type', type=str, 
                       choices=['daily', 'daily_basic', 'adj_factor', 'income', 
                               'balancesheet', 'cashflow', 'index', 'stock_info', 
                               'trade_calendar', 'financial', 'all'],
                       default='daily', help='数据类型')
    
    # 日期参数
    parser.add_argument('--start-date', type=str, help='开始日期 YYYYMMDD')
    parser.add_argument('--end-date', type=str, help='结束日期 YYYYMMDD')
    
    # 指数代码
    parser.add_argument('--index-code', type=str, help='指数代码，如 000001.SH')
    
    # 股票代码 (用于财务数据)
    parser.add_argument('--ts-code', type=str, help='股票代码，如 600000.SH')
    
    # 其他参数
    parser.add_argument('--db', type=str, default=DB_PATH, help='数据库路径')
    parser.add_argument('--workers', type=int, default=cpu_count() - 1 or 4, help='并行进程数')
    parser.add_argument('--parallel', action='store_true', help='使用并行模式更新日线数据')
    parser.add_argument('--source', type=str, choices=['tushare', 'baostock'],
                        default=None, help='指定数据源')
    
    args = parser.parse_args()
    
    # 初始化fetcher
    source = args.source or os.environ.get('DATA_SOURCE', 'tushare')
    fetcher = DWDFetcher(db_path=args.db, source=source)
    
    # 确定日期范围
    end_date = args.end_date or datetime.now().strftime('%Y%m%d')
    start_date = args.start_date
    
    if args.date:
        # 单日模式
        start_date = args.date
        end_date = args.date
    
    # 增量更新模式
    if args.incremental:
        if args.data_type == 'all':
            print("开始增量更新所有数据...")
            total_records = 0
            
            # 1. 交易日历 (不支持增量，用全量)
            print("\n[1/5] 更新交易日历 (全量)...")
            if not start_date:
                start_date = '20200101'
            result_cal = fetcher.update_trade_calendar(start_date, end_date)
            print(f"  交易日历: {result_cal['records']}条")
            total_records += result_cal['records']
            
            # 2. 股票信息 (不支持增量，用全量)
            print("\n[2/5] 更新股票信息 (全量)...")
            result_info = fetcher.update_stock_info(source=source)
            print(f"  股票信息: {result_info['records']}条")
            total_records += result_info['records']
            
            # 3. 日线数据 (增量)
            print("\n[3/5] 更新日线数据 (增量)...")
            result_daily = fetcher.update_incremental('daily')
            print(f"  日线数据: {result_daily['records']}条, 成功{result_daily.get('success', 0)}天")
            total_records += result_daily['records']
            
            # 4. 每日指标 (增量)
            print("\n[4/5] 更新每日指标 (增量)...")
            result_basic = fetcher.update_incremental('daily_basic')
            print(f"  每日指标: {result_basic['records']}条, 成功{result_basic.get('success', 0)}天")
            total_records += result_basic['records']
            
            # 5. 指数日线 (增量)
            print("\n[5/5] 更新指数日线 (增量)...")
            total_index_records = 0
            for idx in fetcher.DEFAULT_INDICES:
                result_idx = fetcher.update_incremental('index')
                total_index_records += result_idx['records']
            print(f"  指数日线: {total_index_records}条")
            total_records += total_index_records
            
            print(f"\n增量更新完成! 总记录: {total_records}条")
        else:
            print(f"开始增量更新: {args.data_type}...")
            result = fetcher.update_incremental(args.data_type)
            print(f"\n{args.data_type} 增量更新完成:")
            print(f"  成功天数: {result.get('success', 0)}")
            print(f"  失败天数: {result.get('fail', 0)}")
            print(f"  记录数: {result.get('records', 0)}")
            print(f"  耗时: {result.get('elapsed', 0):.1f}秒")
        return
    
    # 执行更新
    if args.data_type == 'daily':
        if not start_date:
            start_date = '20260101'
        if args.parallel:
            result = fetcher.update_daily_parallel(start_date, end_date, num_workers=args.workers)
        else:
            result = fetcher.update_daily(start_date, end_date)
        print(f"\n日线数据更新完成:")
        print(f"  成功天数: {result['success']}")
        print(f"  失败天数: {result['fail']}")
        print(f"  记录数: {result['records']}")
        print(f"  耗时: {result['elapsed']:.1f}秒")
        
    elif args.data_type == 'daily_basic':
        if not start_date:
            start_date = '20260101'
        result = fetcher.update_daily_basic(start_date, end_date)
        print(f"\n每日指标更新完成:")
        print(f"  成功天数: {result['success']}")
        print(f"  失败天数: {result['fail']}")
        print(f"  记录数: {result['records']}")
        print(f"  耗时: {result['elapsed']:.1f}秒")
        
    elif args.data_type == 'adj_factor':
        if not start_date:
            start_date = '20200101'
        result = fetcher.update_adj_factor(start_date, end_date)
        print(f"\n复权因子更新完成:")
        print(f"  成功股票: {result['success']}")
        print(f"  失败股票: {result['fail']}")
        print(f"  记录数: {result['records']}")
        print(f"  耗时: {result['elapsed']:.1f}秒")
        
    elif args.data_type == 'income':
        if not args.ts_code:
            print("错误: --ts-code 参数必需")
            return
        result = fetcher.update_income(args.ts_code)
        print(f"\n利润表更新完成:")
        print(f"  股票: {args.ts_code}")
        print(f"  记录数: {result['records']}")
        
    elif args.data_type == 'balancesheet':
        if not args.ts_code:
            print("错误: --ts-code 参数必需")
            return
        result = fetcher.update_balancesheet(args.ts_code)
        print(f"\n资产负债表更新完成:")
        print(f"  股票: {args.ts_code}")
        print(f"  记录数: {result['records']}")
        
    elif args.data_type == 'cashflow':
        if not args.ts_code:
            print("错误: --ts-code 参数必需")
            return
        result = fetcher.update_cashflow(args.ts_code)
        print(f"\n现金流量表更新完成:")
        print(f"  股票: {args.ts_code}")
        print(f"  记录数: {result['records']}")
        
    elif args.data_type == 'index':
        index_code = args.index_code or '000001.SH'
        if not start_date:
            start_date = '20260101'
        result = fetcher.update_index(index_code, start_date, end_date)
        print(f"\n指数日线更新完成:")
        print(f"  指数: {index_code}")
        print(f"  记录数: {result['records']}")
        print(f"  耗时: {result['elapsed']:.1f}秒")
        
    elif args.data_type == 'stock_info':
        result = fetcher.update_stock_info()
        print(f"\n股票信息更新完成:")
        print(f"  记录数: {result['records']}")
        print(f"  耗时: {result['elapsed']:.1f}秒")
        
    elif args.data_type == 'trade_calendar':
        if not start_date:
            start_date = '20200101'
        result = fetcher.update_trade_calendar(start_date, end_date)
        print(f"\n交易日历更新完成:")
        print(f"  记录数: {result['records']}")
        print(f"  耗时: {result['elapsed']:.1f}秒")
        
    elif args.data_type == 'financial':
        result = fetcher.update_financial_multiprocess(num_workers=args.workers)
        print(f"\n财务数据更新完成:")
        print(f"  利润表记录: {result['income_records']}")
        print(f"  资产负债表记录: {result['balancesheet_records']}")
        print(f"  现金流量表记录: {result['cashflow_records']}")
        print(f"  耗时: {result['elapsed']:.1f}秒")
        
    elif args.data_type == 'all':
        # 全量更新所有数据
        print("开始全量更新所有数据...")
        
        # 1. 交易日历
        print("\n[1/8] 更新交易日历...")
        if not start_date:
            start_date = '20240101'
        result_cal = fetcher.update_trade_calendar(start_date, end_date)
        print(f"  交易日历: {result_cal['records']}条")
        
        # 2. 股票信息
        print("\n[2/8] 更新股票信息...")
        result_info = fetcher.update_stock_info(source=source)
        print(f"  股票信息: {result_info['records']}条")
        
        # 3. 日线数据
        print("\n[3/8] 更新日线数据...")
        if not start_date:
            start_date = '20240101'
        result_daily = fetcher.update_daily(start_date, end_date)
        print(f"  日线数据: {result_daily['records']}条, 成功{result_daily['success']}天")
        
        # 4. 每日指标
        print("\n[4/8] 更新每日指标...")
        result_basic = fetcher.update_daily_basic(start_date, end_date)
        print(f"  每日指标: {result_basic['records']}条, 成功{result_basic['success']}天")
        
        # 5. 复权因子
        print("\n[5/8] 更新复权因子...")
        result_adj = fetcher.update_adj_factor(start_date, end_date)
        print(f"  复权因子: {result_adj['records']}条")
        
        # 6. 指数日线
        print("\n[6/8] 更新指数日线...")
        total_index_records = 0
        for idx in DWDFetcher.DEFAULT_INDICES:
            result_idx = fetcher.update_index(idx, start_date, end_date)
            total_index_records += result_idx['records']
        print(f"  指数日线: {total_index_records}条")
        
        # 7. 财务数据
        print("\n[7/8] 更新财务数据 (多进程)...")
        result_financial = fetcher.update_financial_multiprocess(num_workers=args.workers)
        print(f"  财务数据: 利润表{result_financial['income_records']}条, "
              f"资产负债表{result_financial['balancesheet_records']}条, "
              f"现金流量表{result_financial['cashflow_records']}条")
        
        print("\n全量更新完成!")


if __name__ == "__main__":
    run_cli()

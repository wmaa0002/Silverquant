"""
Baostock日线数据获取器

从baostock获取日线OHLCV数据，支持:
- 按股票代码获取指定区间数据
- 自动代码格式转换 (300486.SZ ↔ sz.300486)
- 字段映射到dwd_daily_price格式

注意: baostock的volume和amount已经是最终单位(股/元)，无需转换
"""

import logging
import pandas as pd
import baostock as bs
from typing import Optional, Union

from data.fetchers.baostock_adapter.base import BaostockBaseFetcher
from data.fetchers.baostock_adapter.code_converter import (
    convert_code_to_baostock,
    convert_code_from_baostock,
)

logger = logging.getLogger(__name__)


class BaostockDailyPriceFetcher(BaostockBaseFetcher):
    """
    Baostock日线数据获取器
    
    使用示例:
        fetcher = BaostockDailyPriceFetcher()
        
        # 获取单只股票区间数据
        df = fetcher.fetch_by_code('300486', '20260301', '20260330')
        
        # 或使用上下文管理器
        with BaostockDailyPriceFetcher() as fetcher:
            df = fetcher.fetch_by_code('300486.SZ', '20260301', '20260330')
    """
    
    # baostock 查询字段
    FIELDS = 'date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST'
    
    def fetch_by_code(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjustflag: str = '3'
    ) -> pd.DataFrame:
        """
        获取指定股票的日线数据区间
        
        Args:
            code: 股票代码 (支持格式: '300486', '300486.SZ', 'sz.300486')
            start_date: 开始日期 (YYYYMMDD 或 YYYY-MM-DD)
            end_date: 结束日期 (YYYYMMDD 或 YYYY-MM-DD)
            adjustflag: 复权状态 (1=后复权, 2=前复权, 3=不复权)
        
        Returns:
            DataFrame with columns:
                - ts_code: 股票代码 (300486.SZ)
                - trade_date: 交易日期 (YYYY-MM-DD)
                - open, high, low, close: 价格
                - vol: 成交量 (股)
                - amount: 成交额 (元)
                - pct_chg: 涨跌幅 (%)
                - data_source: 'baostock_{adjustflag}'
        """
        # 转换代码格式
        bs_code = convert_code_to_baostock(code)
        
        # 转换日期格式
        start_str = self._parse_date(start_date)
        end_str = self._parse_date(end_date)
        
        logger.info(f"获取日线数据: {code} ({bs_code}), 区间={start_str}~{end_str}")
        
        # 执行查询
        rs = bs.query_history_k_data_plus(
            bs_code,
            self.FIELDS,
            start_date=start_str,
            end_date=end_str,
            frequency='d',
            adjustflag=adjustflag
        )
        
        if rs.error_code != '0':
            logger.error(f"查询失败: {rs.error_msg}")
            return self._empty_df()
        
        # 提取数据
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            logger.warning(f"无数据返回: {code}")
            return self._empty_df()
        
        # 构建DataFrame
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 转换格式
        df = self._convert_to_dwd_format(df, adjustflag)
        
        logger.info(f"获取成功: {code}, {len(df)} 条记录")
        return df
    
    def _parse_date(self, date: Union[str, int]) -> str:
        """
        解析日期格式为YYYY-MM-DD
        
        Examples:
            '20260301' → '2026-03-01'
            '2026-03-01' → '2026-03-01'
            20260301 → '2026-03-01'
        """
        date_str = str(date)
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str
    
    def _convert_to_dwd_format(self, df: pd.DataFrame, adjustflag: str) -> pd.DataFrame:
        """
        将baostock数据转换为dwd_daily_price格式
        
        baostock字段 → dwd_daily_price字段:
            date → trade_date
            code → ts_code (sz.300486 → 300486.SZ)
            volume → vol
            pctChg → pct_chg
        """
        df = df.copy()
        
        # 重命名字段
        df = df.rename(columns={
            'date': 'trade_date',
            'pctChg': 'pct_chg',
        })
        
        # 转换代码格式: sz.300486 → 300486.SZ
        df['ts_code'] = df['code'].apply(convert_code_from_baostock)
        
        # 添加数据来源标记
        df['data_source'] = f'baostock_{adjustflag}'
        
        # 确保数值类型
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 选择需要的列并按日期排序
        result_cols = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 
                       'volume', 'amount', 'pct_chg', 'data_source']
        result_cols = [c for c in result_cols if c in df.columns]
        
        if len(df) > 0:
            df = df.sort_values('trade_date')
        
        return df[result_cols]
    
    def _empty_df(self) -> pd.DataFrame:
        """返回空DataFrame"""
        return pd.DataFrame(columns=[
            'ts_code', 'trade_date', 'open', 'high', 'low', 'close',
            'volume', 'amount', 'pct_chg', 'data_source'
        ])
"""
Tushare指数数据获取器

提供指数日线数据获取功能，支持 broad market indices。

主要功能:
- fetch(): 获取指数日线数据 (pro.index_daily)

数据字段:
- index_code: 指数代码
- trade_date: 交易日期
- open: 开盘价
- high: 最高价
- low: 最低价
- close: 收盘价
- vol: 成交量 (原单位×100)
- amount: 成交额 (原单位×1000)
- pct_change: 涨跌幅

注意事项:
- 不支持行业指数，只支持 broad market indices
- 不支持分钟级数据

使用示例:
    from data.fetchers.tushare_adapter.index import TushareIndexFetcher

    fetcher = TushareIndexFetcher()
    df = fetcher.fetch('000001.SH', '20240101', '20240330')
"""

import sys
import os
from typing import Optional

import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from data.fetchers.tushare_adapter.base import TushareBaseFetcher


class TushareIndexFetcher(TushareBaseFetcher):
    """
    Tushare指数数据获取器

    继承自TushareBaseFetcher，提供指数日线数据获取能力。

    主要方法:
        fetch(): 获取指定指数在日期范围内的日线数据
    """

    def fetch(
        self,
        index_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取指数日线数据

        Args:
            index_code: 指数代码，如 '000001.SH'（上证指数）、'399001.SZ'（深证成指）
            start_date: 开始日期，格式 'YYYYMMDD'，可选
            end_date: 结束日期，格式 'YYYYMMDD'，可选

        Returns:
            DataFrame，字段包括:
            - index_code: 指数代码
            - trade_date: 交易日期
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - close: 收盘价
            - vol: 成交量（原单位×100）
            - amount: 成交额（原单位×1000）
            - pct_change: 涨跌幅

        Raises:
            RuntimeError: API未初始化或调用失败

        注意:
            - 只支持 broad market indices，不支持行业指数
            - vol和amount已完成单位转换（×100和×1000）
        """
        # 解析日期参数
        start_str = self._parse_date(start_date) if start_date else None
        end_str = self._parse_date(end_date) if end_date else None

        # 调用API
        result = self._call_api(
            self.api.index_daily,
            ts_code=index_code,
            start_date=start_str,
            end_date=end_str
        )

        if result is None or result.empty:
            return pd.DataFrame()

        # 单位转换: vol×100, amount×1000
        df = result.copy()
        if 'vol' in df.columns:
            df['vol'] = df['vol'] * 100
        if 'amount' in df.columns:
            df['amount'] = df['amount'] * 1000

        # 重命名字段以保持一致性
        if 'ts_code' in df.columns:
            df = df.rename(columns={'ts_code': 'index_code'})

        if 'pct_chg' in df.columns:
            df = df.rename(columns={'pct_chg': 'pct_change'})

        return df

"""
Tushare日线数据获取器

从tushare pro获取日线OHLCV数据，支持:
- 按日期获取全市场数据
- 按股票代码获取指定区间数据
- 自动单位转换 (手→股, 千元→元)
- 速率限制和重试机制

依赖:
    - TushareBaseFetcher: 提供API调用基础设施
    - tushare_limiter: 速率限制器

单位转换:
    - tushare vol: 手 (hand) → 数据库: 股 (share) = vol * 100
    - tushare amount: 千元 → 数据库: 元 = amount * 1000
"""

import logging
from typing import Optional, Union

import pandas as pd

from data.fetchers.tushare_adapter.base import TushareBaseFetcher

logger = logging.getLogger(__name__)


class TushareDailyPriceFetcher(TushareBaseFetcher):
    """
    Tushare日线数据获取器

    继承自TushareBaseFetcher，提供:
    - 自动token管理
    - 速率限制（50次/分钟）
    - 重试机制（3次，指数退避）
    - 429错误处理

    使用示例:
        fetcher = TushareDailyPriceFetcher()
        # 获取单日全市场数据
        df = fetcher.fetch_by_date('2026-04-03')
        # 获取单只股票区间数据
        df = fetcher.fetch_by_code('000001.SZ', '20260101', '20260406')
    """

    def fetch_by_date(self, trade_date: Union[str, int]) -> pd.DataFrame:
        """
        获取指定日期的全市场日线数据

        Args:
            trade_date: 交易日期，支持格式:
                - str: '20260403', '2026-04-03', '2026/04/03'
                - int: 20260403

        Returns:
            DataFrame with columns:
                - ts_code: 股票代码 (e.g. '000001.SZ')
                - trade_date: 交易日期 (YYYYMMDD)
                - open: 开盘价
                - high: 最高价
                - low: 最低价
                - close: 收盘价
                - vol: 成交量 (股) [已转换: tushare手×100]
                - amount: 成交额 (元) [已转换: tushare千元×1000]
                - pct_chg: 涨跌幅 (%)

        Raises:
            RuntimeError: API未初始化或调用失败
        """
        date_str = self._parse_date(trade_date)

        logger.info(f"获取日线数据: 日期={date_str}")

        def api_call():
            return self.api.daily(trade_date=date_str)

        df = self._call_api(api_call)

        if df is None or df.empty:
            logger.warning(f"指定日期 {date_str} 无日线数据")
            return pd.DataFrame(columns=[
                'ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount', 'pct_chg'
            ])

        # 单位转换: tushare手→股, 千元→元
        df = self._convert_units(df)

        # 确保返回字段完整
        df = self._ensure_columns(df)

        logger.info(f"获取日线数据成功: 日期={date_str}, 股票数={len(df)}")
        return df

    def fetch_by_code(
        self,
        ts_code: str,
        start_date: Union[str, int],
        end_date: Union[str, int]
    ) -> pd.DataFrame:
        """
        获取指定股票代码的日线数据区间

        Args:
            ts_code: 股票代码 (e.g. '000001.SZ', '600000.SH')
            start_date: 开始日期，支持格式:
                - str: '20260101', '2026-01-01', '2026/01/01'
                - int: 20260101
            end_date: 结束日期，支持同上格式

        Returns:
            DataFrame with columns:
                - ts_code: 股票代码
                - trade_date: 交易日期 (YYYYMMDD)
                - open: 开盘价
                - high: 最高价
                - low: 最低价
                - close: 收盘价
                - vol: 成交量 (股) [已转换]
                - amount: 成交额 (元) [已转换]
                - pct_chg: 涨跌幅 (%)

        Raises:
            RuntimeError: API未初始化或调用失败
        """
        start_str = self._parse_date(start_date)
        end_str = self._parse_date(end_date)

        logger.info(f"获取日线数据: 代码={ts_code}, 区间={start_str}~{end_str}")

        def api_call():
            return self.api.daily(ts_code=ts_code, start_date=start_str, end_date=end_str)

        df = self._call_api(api_call)

        if df is None or df.empty:
            logger.warning(f"指定区间 {ts_code} {start_str}~{end_str} 无日线数据")
            return pd.DataFrame(columns=[
                'ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount', 'pct_chg'
            ])

        # 单位转换
        df = self._convert_units(df)

        # 确保返回字段完整
        df = self._ensure_columns(df)

        logger.info(f"获取日线数据成功: 代码={ts_code}, 区间={start_str}~{end_str}, 天数={len(df)}")
        return df

    def _convert_units(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        单位转换: tushare返回的原始单位转换为数据库标准单位

        tushare单位:
            - vol: 手 (hand, 100股)
            - amount: 千元 (thousand yuan)

        数据库标准:
            - vol: 股 (share)
            - amount: 元 (yuan)

        Args:
            df: tushare原始数据

        Returns:
            转换后的DataFrame
        """
        df = df.copy()

        # tushare volume: 手 → 数据库: 股 (×100)
        if 'vol' in df.columns:
            df['vol'] = pd.to_numeric(df['vol'], errors='coerce') * 100

        # tushare amount: 千元 → 数据库: 元 (×1000)
        if 'amount' in df.columns:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce') * 1000

        return df

    def _ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        确保返回DataFrame包含所有必需字段

        Args:
            df: 转换后的数据

        Returns:
            包含所有必需字段的DataFrame
        """
        required_cols = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount', 'pct_chg']

        for col in required_cols:
            if col not in df.columns:
                df[col] = None

        # 按日期排序
        if 'trade_date' in df.columns and len(df) > 0:
            df = df.sort_values('trade_date')

        return df[required_cols]

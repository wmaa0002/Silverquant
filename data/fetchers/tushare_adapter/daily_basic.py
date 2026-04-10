"""
Tushare每日指标获取器

提供每日市场指标数据获取功能，包括PE、PB、换手率等。

主要功能:
- fetch_by_date(): 获取指定交易日的所有股票每日指标

数据字段:
- trade_date: 交易日期
- ts_code: 股票代码
- close: 收盘价
- pe_ttm: 市盈率TTM
- pe: 市盈率
- ps_ttm: 市销率TTM
- ps: 市销率
- pcf: 市现率
- pb: 市净率
- total_mv: 总市值
- circ_mv: 流通市值
- amount: 成交额
- turn_rate: 换手率

使用示例:
    from data.fetchers.tushare_adapter.daily_basic import TushareDailyBasicFetcher

    fetcher = TushareDailyBasicFetcher()
    df = fetcher.fetch_by_date('20240330')
"""

import sys
import os
from typing import Optional

import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from data.fetchers.tushare_adapter.base import TushareBaseFetcher


class TushareDailyBasicFetcher(TushareBaseFetcher):
    """
    Tushare每日指标获取器

    继承自TushareBaseFetcher，提供每日市场指标数据获取能力。

    主要方法:
        fetch_by_date(): 获取指定交易日的所有股票每日指标

    用途:
        - 筛选低估值股票（PE、PB、PS等）
        - 计算换手率、量比等技术指标
        - 市值分析和流动性分析
    """

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        """
        获取指定交易日的每日指标数据

        Args:
            trade_date: 交易日期，格式 'YYYYMMDD'

        Returns:
            DataFrame，字段包括:
            - trade_date: 交易日期
            - ts_code: 股票代码
            - close: 收盘价
            - pe_ttm: 市盈率TTM（滚动市盈率）
            - pe: 市盈率（静态市盈率）
            - ps_ttm: 市销率TTM
            - ps: 市销率
            - pcf: 市现率（每股现金流）
            - pb: 市净率
            - total_mv: 总市值（万元）
            - circ_mv: 流通市值（万元）
            - amount: 成交额（千元）
            - turn_rate: 换手率（%）

        Raises:
            RuntimeError: API未初始化或调用失败

        注意:
            - 返回该交易日所有股票的指标数据
            - 单位说明:
              - total_mv, circ_mv: 万元
              - amount: 千元
              - turn_rate: %
        """
        # 解析日期参数
        trade_date_str = self._parse_date(trade_date)

        # 调用API
        result = self._call_api(
            self.api.daily_basic,
            trade_date=trade_date_str
        )

        if result is None or result.empty:
            return pd.DataFrame()

        # 选择需要的字段
        fields = [
            'trade_date', 'ts_code', 'close',
            'pe_ttm', 'pe', 'ps_ttm', 'ps', 'pcf', 'pb',
            'total_mv', 'circ_mv', 'amount', 'turn_rate'
        ]
        available_fields = [f for f in fields if f in result.columns]

        return result[available_fields].copy()

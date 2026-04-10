"""
Tushare适配器模块

提供Tushare API调用的基础设施类，供具体数据接口继承使用。

主要组件:
- TushareBaseFetcher: 基类，提供token管理、速率限制、重试机制
- TushareIndexFetcher: 指数日线数据获取器
- TushareAdjFactorFetcher: 复权因子获取器
- TushareDailyBasicFetcher: 每日指标获取器
- TushareTradeCalFetcher: 交易日历获取器
"""

from data.fetchers.tushare_adapter.base import TushareBaseFetcher
from data.fetchers.tushare_adapter.daily import TushareDailyPriceFetcher
from data.fetchers.tushare_adapter.financial import (
    TushareIncomeFetcher,
    TushareBalanceSheetFetcher,
    TushareCashFlowFetcher,
)
from data.fetchers.tushare_adapter.index import TushareIndexFetcher
from data.fetchers.tushare_adapter.adj_factor import TushareAdjFactorFetcher
from data.fetchers.tushare_adapter.daily_basic import TushareDailyBasicFetcher
from data.fetchers.tushare_adapter.trade_cal import TushareTradeCalFetcher

__all__ = [
    'TushareBaseFetcher',
    'TushareDailyPriceFetcher',
    'TushareIncomeFetcher',
    'TushareBalanceSheetFetcher',
    'TushareCashFlowFetcher',
    'TushareIndexFetcher',
    'TushareAdjFactorFetcher',
    'TushareDailyBasicFetcher',
    'TushareTradeCalFetcher',
]
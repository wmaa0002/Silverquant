"""
Baostock适配器模块

提供Baostock API调用的基础设施类，供具体数据接口继承使用。

主要组件:
- BaostockBaseFetcher: 基类，提供session管理、错误处理
- BaostockDailyPriceFetcher: 日线数据获取器
- BaostockStockInfoFetcher: 股票信息获取器
"""

from data.fetchers.baostock_adapter.base import BaostockBaseFetcher
from data.fetchers.baostock_adapter.daily import BaostockDailyPriceFetcher
from data.fetchers.baostock_adapter.stock_info import BaostockStockInfoFetcher
from data.fetchers.baostock_adapter.code_converter import (
    convert_code_to_baostock,
    convert_code_from_baostock,
)

__all__ = [
    'BaostockBaseFetcher',
    'BaostockDailyPriceFetcher',
    'BaostockStockInfoFetcher',
    'convert_code_to_baostock',
    'convert_code_from_baostock',
]
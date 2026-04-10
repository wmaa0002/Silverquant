"""
市场数据模块 - markets

支持多市场股票数据获取：
- China A-Stocks (沪深市场)
- Hong Kong Stocks (港股)
- US Stocks (美股)
"""

from .hk_stocks import HKStockData
from .us_stocks import USStockData
from .router import MarketRouter

__all__ = [
    'HKStockData',
    'USStockData',
    'MarketRouter',
]
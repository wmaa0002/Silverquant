"""
Tushare交易日历获取器

提供交易所交易日历数据获取功能。

主要功能:
- fetch(): 获取指定日期范围内的交易日历

数据字段:
- trade_date: 交易日期
- exchange: 交易所代码 (SSE/SZSE/CFFEX/INE/SHFE/DCE)
- is_open: 是否交易日 (1: 是, 0: 否)

使用示例:
    from data.fetchers.tushare_adapter.trade_cal import TushareTradeCalFetcher

    fetcher = TushareTradeCalFetcher()
    df = fetcher.fetch('20240101', '20240330')
"""

import sys
import os
from typing import Optional

import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from data.fetchers.tushare_adapter.base import TushareBaseFetcher


class TushareTradeCalFetcher(TushareBaseFetcher):
    """
    Tushare交易日历获取器

    继承自TushareBaseFetcher，提供交易日历数据获取能力。

    主要方法:
        fetch(): 获取指定日期范围内的交易日历

    用途:
        - 获取交易日列表用于批量数据下载
        - 判断指定日期是否为交易日
        - 断点续传时确定下一个交易日
    """

    def fetch(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        exchange: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取交易日历数据

        Args:
            start_date: 开始日期，格式 'YYYYMMDD'，可选
            end_date: 结束日期，格式 'YYYYMMDD'，可选
            exchange: 交易所代码，可选。常用值:
                - 'SSE': 上海证券交易所
                - 'SZSE': 深圳证券交易所
                - 'CFFEX': 中国金融期货交易所
                - 'INE': 上海国际能源交易中心
                - 'SHFE': 上海期货交易所
                - 'DCE': 大连商品交易所
                - None: 返回所有交易所日历

        Returns:
            DataFrame，字段包括:
            - trade_date: 交易日期
            - exchange: 交易所代码
            - is_open: 是否交易日 (1: 是, 0: 否)

        Raises:
            RuntimeError: API未初始化或调用失败

        注意:
            - 如果不指定exchange，返回所有交易所的数据
            - 可以通过 is_open 字段筛选交易日
        """
        # 解析日期参数
        start_str = self._parse_date(start_date) if start_date else None
        end_str = self._parse_date(end_date) if end_date else None

        # 调用API
        result = self._call_api(
            self.api.trade_cal,
            start_date=start_str,
            end_date=end_str,
            exchange=exchange
        )

        if result is None or result.empty:
            return pd.DataFrame()

        # 选择需要的字段，并重命名cal_date为trade_date
        fields = ['cal_date', 'exchange', 'is_open']
        available_fields = [f for f in fields if f in result.columns]
        df = result[available_fields].copy()
        
        # 重命名cal_date为trade_date
        if 'cal_date' in df.columns:
            df = df.rename(columns={'cal_date': 'trade_date'})
        
        return df

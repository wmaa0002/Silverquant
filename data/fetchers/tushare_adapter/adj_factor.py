"""
Tushare复权因子获取器

提供复权因子数据获取功能，用于计算前复权/后复权价格。

主要功能:
- fetch(): 获取指定股票的复权因子

数据字段:
- ts_code: 股票代码
- trade_date: 交易日期
- adj_factor: 复权因子

使用示例:
    from data.fetchers.tushare_adapter.adj_factor import TushareAdjFactorFetcher

    fetcher = TushareAdjFactorFetcher()
    df = fetcher.fetch('600000.SH', '20240101', '20240330')
"""

import sys
import os
from typing import Optional

import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from data.fetchers.tushare_adapter.base import TushareBaseFetcher


class TushareAdjFactorFetcher(TushareBaseFetcher):
    """
    Tushare复权因子获取器

    继承自TushareBaseFetcher，提供复权因子数据获取能力。

    主要方法:
        fetch(): 获取指定股票在日期范围内的复权因子

    用途:
        复权因子用于计算前复权/后复权价格:
        - 前复权价格 = 未复权价格 × 复权因子
        - 后复权价格 = 未复权价格 ÷ 复权因子
    """

    def fetch(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取复权因子数据

        Args:
            ts_code: 股票代码，如 '600000.SH'
            start_date: 开始日期，格式 'YYYYMMDD'，可选
            end_date: 结束日期，格式 'YYYYMMDD'，可选

        Returns:
            DataFrame，字段包括:
            - ts_code: 股票代码
            - trade_date: 交易日期
            - adj_factor: 复权因子

        Raises:
            RuntimeError: API未初始化或调用失败

        注意:
            - 可以通过 trade_date 指定单日数据
            - 复权因子是累计值，用于价格调整
        """
        # 解析日期参数
        start_str = self._parse_date(start_date) if start_date else None
        end_str = self._parse_date(end_date) if end_date else None

        # 调用API
        result = self._call_api(
            self.api.adj_factor,
            ts_code=ts_code,
            start_date=start_str,
            end_date=end_str
        )

        if result is None or result.empty:
            return pd.DataFrame()

        return result[['ts_code', 'trade_date', 'adj_factor']].copy()

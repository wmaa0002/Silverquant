"""
Baostock股票信息获取器

从baostock获取A股股票基本信息，包括:
- 股票代码 (sh.600000, sz.000001)
- 股票名称
- 上市日期
- 退市日期
- 市场类型
- 上市状态
"""

import logging
import pandas as pd
import baostock as bs

from data.fetchers.baostock_adapter.base import BaostockBaseFetcher
from data.fetchers.baostock_adapter.code_converter import convert_code_from_baostock

logger = logging.getLogger(__name__)


class BaostockStockInfoFetcher(BaostockBaseFetcher):
    """
    Baostock股票信息获取器

    使用示例:
        fetcher = BaostockStockInfoFetcher()
        df = fetcher.fetch_all()
    """

    def fetch_all(self) -> pd.DataFrame:
        """
        获取所有A股股票基本信息

        Returns:
            DataFrame with columns:
                - code: 股票代码 (300486.SZ)
                - name: 股票名称
                - listing_date: 上市日期 (YYYY-MM-DD)
                - delist_date: 退市日期 (YYYY-MM-DD, 无则空)
                - type: 股票类型 (1=股票, 4=转债, 5=ETF)
                - status: 上市状态 (1=上市, 0=退市)
        """
        logger.info("获取全量股票信息...")

        rs = bs.query_stock_basic(code_name=None)

        if rs.error_code != '0':
            logger.error(f"查询失败: {rs.error_msg}")
            return self._empty_df()

        # 提取数据
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            logger.warning("无股票信息返回")
            return self._empty_df()

        # 构建DataFrame
        df = pd.DataFrame(data_list, columns=rs.fields)

        # 过滤：只获取上市(status='1')的股票(type='1')
        # baostock status: 1=上市, 0=退市
        # baostock type: 1=股票, 2=指数, 4=转债, 5=ETF
        df = df[(df['status'] == '1') & (df['type'] == '1')]

        if df.empty:
            logger.warning("无上市股票信息返回")
            return self._empty_df()

        # 转换格式
        df = self._convert_format(df)

        logger.info(f"获取成功, {len(df)} 只股票")
        return df

    def _convert_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        转换baostock数据格式

        baostock字段:
            - code: sh.600000, sz.000001
            - code_name: 股票名称
            - ipoDate: 上市日期
            - outDate: 退市日期
            - type: 类型 (1=股票, 2=指数, 4=转债, 5=ETF)
            - status: 状态 (1=上市, 0=退市)

        映射到dwd_stock_info:
            - code -> ts_code
            - code_name -> name
            - ipoDate -> listing_date
            - outDate -> delist_date
            - type -> market (1=主板, 4=转债, 5=ETF)
            - status -> list_status (1=L, 0=D)
        """
        df = df.copy()

        # 转换代码格式: sh.600000 → 600000.SH, sz.000001 → 000001.SZ
        df['code'] = df['code'].apply(convert_code_from_baostock)

        # 重命名列
        df = df.rename(columns={
            'code': 'ts_code',
            'code_name': 'name',
            'ipoDate': 'listing_date',
            'outDate': 'delist_date'
        })

        # 提取 symbol (纯数字代码)
        df['symbol'] = df['ts_code'].apply(lambda x: x.split('.')[0] if '.' in x else x)

        # 映射 type -> market
        # baostock: 1=股票, 2=指数, 4=转债, 5=ETF
        # dwd_stock_info: 主板, 指数, 转债, ETF
        type_map = {
            '1': '主板',    # A股股票
            '2': '指数',    # 指数
            '4': '转债',    # 转债
            '5': 'ETF',     # ETF
        }
        df['market'] = df['type'].map(type_map).fillna('未知')

        # 映射 status -> list_status
        # baostock: 1=上市, 0=退市
        # dwd_stock_info: L=上市, D=退市
        status_map = {
            '1': 'L',  # 上市
            '0': 'D',  # 退市
        }
        df['list_status'] = df['status'].map(status_map).fillna('D')

        # 添加缺失字段 (baostock不提供，设为None)
        df['area'] = None
        df['industry'] = None
        df['is_hs'] = None
        df['act_name'] = None
        df['data_source'] = 'baostock'

        # 选择需要的列 (与dwd_stock_info表结构一致)
        result_cols = [
            'ts_code', 'symbol', 'name', 'area', 'industry', 'market',
            'listing_date', 'is_hs', 'act_name', 'list_status', 'delist_date', 'data_source'
        ]
        return df[result_cols]

    def _empty_df(self) -> pd.DataFrame:
        return pd.DataFrame(columns=[
            'ts_code', 'symbol', 'name', 'area', 'industry', 'market',
            'listing_date', 'is_hs', 'act_name', 'list_status', 'delist_date', 'data_source'
        ])
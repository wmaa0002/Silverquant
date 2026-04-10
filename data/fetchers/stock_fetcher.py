"""
[DEPRECATED] 请使用 data.updaters.fetcher_dwd.DWDFetcher

废弃日期: 2026-04-07
原因: 已被 fetcher_dwd.py 统一管理

注意: DWDFetcher 用于更新数据库，此文件用于获取数据（get_stock_list, get_daily_price 等方法）

迁移指南:
- 如需获取数据: 保留此文件
- 如需更新数据库: 使用 DWDFetcher
股票数据获取器 - 支持akshare、baostock和tushare三数据源
"""
import akshare as ak
import baostock as bs
import pandas as pd
import tushare as ts
from typing import List, Optional
from datetime import datetime, date, timedelta
import time
import sys
import os
import logging

# 导入配置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config.settings import Settings
from data.fetchers.rate_limiter import tushare_limiter
from data.fetchers.baostock_adapter.code_converter import to_tushare, from_tushare

logger = logging.getLogger(__name__)


class StockFetcher:
    """股票数据获取器 - 支持多数据源"""
    
    SOURCE_AKSHARE = 'akshare'
    SOURCE_BAOSTOCK = 'baostock'
    SOURCE_TUSHARE = 'tushare'
    
    def __init__(self, source: Optional[str] = None):
        """初始化数据获取器"""
        self.rate_limit_delay = 0.1
        self.source = source or Settings.DATA_SOURCE
        
        self._bs_logged_in = False
        self._tushare_pro = None
        
    def __del__(self):
        """析构时登出baostock"""
        if self._bs_logged_in:
            try:
                bs.logout()
            except Exception as e:
                logger.warning(f"baostock登出失败: {e}")
    
    def _ensure_bs_login(self):
        """确保baostock已登录"""
        if not self._bs_logged_in:
            lg = bs.login()
            if lg.error_code != '0':
                raise Exception(f"baostock登录失败: {lg.error_msg}")
            self._bs_logged_in = True
    
    def _ensure_tushare_login(self):
        """确保tushare已登录并初始化pro API"""
        if self._tushare_pro is None:
            token = Settings.TUSHARE_TOKEN
            if not token:
                logger.warning("TUSHARE_TOKEN未设置，无法使用tushare数据源")
                return False
            ts.set_token(token)
            self._tushare_pro = ts.pro_api()
        return True
    
    def _safe_call(self, func, *args, **kwargs):
        """安全调用API，带重试机制"""
        max_retries = 3
        for i in range(max_retries):
            try:
                time.sleep(self.rate_limit_delay)
                return func(*args, **kwargs)
            except Exception as e:
                if i == max_retries - 1:
                    print(f"API调用失败（已重试{max_retries}次）: {e}")
                    raise
                time.sleep(1 * (i + 1))  # 指数退避
    
    # ==================== 股票基础信息 ====================
    
    def get_stock_list(self) -> pd.DataFrame:
        """获取A股所有股票列表"""
        if self.source == self.SOURCE_BAOSTOCK:
            return self._get_stock_list_baostock()
        elif self.source == self.SOURCE_TUSHARE:
            return self._get_stock_list_tushare()
        else:
            return self._get_stock_list_akshare()
    
    def _get_stock_list_akshare(self) -> pd.DataFrame:
        """使用akshare获取股票列表"""
        df = self._safe_call(ak.stock_zh_a_spot_em)
        
        # 标准化列名
        column_mapping = {
            '代码': 'code',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'change_pct',
            '总市值': 'market_cap',
            '流通市值': 'circulating_cap',
        }
        df = df.rename(columns=column_mapping)
        
        # 提取市场类型
        df['market_type'] = df['code'].apply(self._get_market_type)
        df['is_st'] = df['name'].str.contains('ST', na=False)
        
        return df[['code', 'name', 'market_type', 'market_cap', 'circulating_cap', 'is_st']]
    
    def _get_stock_list_baostock(self) -> pd.DataFrame:
        """使用baostock获取股票列表"""
        self._ensure_bs_login()
        
        rs = bs.query_stock_basic()
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            return pd.DataFrame(columns=['code', 'name', 'market_type', 'market_cap', 'circulating_cap', 'is_st'])
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 过滤只保留A股（沪市sh.和深市sz.）
        df = df[df['code'].str.match(r'^(sh|sz)\.[0-9]{6}$')]
        # 过滤只保留股票 (type=1)，排除指数/债券/基金
        df = df[df['type'] == '1']
        
        # 提取市场类型
        df['market_type'] = df['code'].apply(self._get_market_type_baostock)
        df['is_st'] = df['code_name'].str.contains('ST', na=False)
        
        # 标准化列名
        df = df.rename(columns={'code_name': 'name'})
        df['code'] = df['code'].str.replace('sh.', '').str.replace('sz.', '')
        df['market_cap'] = None
        df['circulating_cap'] = None
        
        return df[['code', 'name', 'market_type', 'market_cap', 'circulating_cap', 'is_st']]
    
    def _get_stock_list_tushare(self) -> pd.DataFrame:
        """使用tushare获取股票列表"""
        if not self._ensure_tushare_login():
            return pd.DataFrame(columns=['code', 'name', 'market_type', 'market_cap', 'circulating_cap', 'is_st'])
        
        tushare_limiter.acquire()
        df = self._safe_call(self._tushare_pro.stock_basic, exchange='', list_status='L')
        
        if df is None or df.empty:
            return pd.DataFrame(columns=['code', 'name', 'market_type', 'market_cap', 'circulating_cap', 'is_st'])
        
        df = df.rename(columns={
            'ts_code': 'code',
            'name': 'name',
            'market': 'market'
        })
        df['code'] = df['code'].apply(from_tushare)
        df['market_type'] = df['code'].apply(self._get_market_type)
        df['is_st'] = df['name'].str.contains('ST', na=False)
        df['market_cap'] = None
        df['circulating_cap'] = None
        
        return df[['code', 'name', 'market_type', 'market_cap', 'circulating_cap', 'is_st']]
    
    def _get_market_type(self, code: str) -> str:
        """判断市场类型 - akshare格式"""
        if code.startswith('688'):
            return '科创板'
        elif code.startswith('300') or code.startswith('301'):
            return '创业板'
        elif code.startswith('8') or code.startswith('4'):
            return '北交所'
        else:
            return '主板'
    
    def _get_market_type_baostock(self, code: str) -> str:
        """判断市场类型 - baostock格式"""
        # code格式: sh.600000, sz.000001
        prefix = code.split('.')[0]
        num = code.split('.')[1]
        
        if num.startswith('688'):
            return '科创板'
        elif num.startswith('300') or num.startswith('301'):
            return '创业板'
        elif num.startswith('8') or num.startswith('4'):
            return '北交所'
        elif prefix == 'sh':
            return '主板（沪市）'
        else:
            return '主板（深市）'
    
    def get_stock_info(self, code: str) -> pd.DataFrame:
        """获取单只股票详细信息"""
        if self.source == self.SOURCE_BAOSTOCK:
            # baostock不提供此功能，使用akshare
            pass
        elif self.source == self.SOURCE_TUSHARE:
            return self._get_stock_info_tushare(code)
        df = self._safe_call(ak.stock_individual_info_em, symbol=code)
        return df
    
    def _get_stock_info_tushare(self, code: str) -> pd.DataFrame:
        """使用tushare获取单只股票详细信息"""
        token = os.environ.get('TUSHARE_TOKEN')
        if not token:
            logger.warning("TUSHARE_TOKEN未设置，使用akshare获取股票信息")
            return self._safe_call(ak.stock_individual_info_em, symbol=code)
        
        ts.set_token(token)
        pro = ts.pro_api()
        
        # tushare股票代码需要转换
        ts_code = to_tushare(code)
        
        df = pro.stock_basic(ts_code=ts_code, fields='ts_code,symbol,name,area,industry,list_date,is_hs')
        if df.empty:
            return pd.DataFrame()
        
        df = df.rename(columns={'symbol': 'code'})
        return df
    
    def get_industry_classification(self) -> pd.DataFrame:
        """获取行业分类"""
        if self.source == self.SOURCE_BAOSTOCK:
            # baostock不提供此功能
            return pd.DataFrame()
        df = self._safe_call(ak.stock_board_industry_name_ths)
        return df
    
    def get_stock_industry(self, code: str) -> str:
        """获取股票所属行业"""
        try:
            df = self._safe_call(ak.stock_sector_detail, sector=code)
            return df.iloc[0]['板块'] if len(df) > 0 else '未知'
        except Exception:
            return '未知'
    
    # ==================== 历史行情数据 ====================
    
    def get_daily_price(
        self, 
        code: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = 'qfq'  # qfq-前复权, hfq-后复权, 不复权
    ) -> pd.DataFrame:
        """获取日线数据"""
        if start_date is None:
            start_date = '20240101'
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        
        if self.source == self.SOURCE_BAOSTOCK:
            return self._get_daily_price_baostock(code, start_date, end_date, adjust)
        elif self.source == self.SOURCE_TUSHARE:
            return self._get_daily_price_tushare(code, start_date, end_date, adjust)
        else:
            return self._get_daily_price_akshare(code, start_date, end_date, adjust)
    
    def _get_daily_price_akshare(
        self, 
        code: str, 
        start_date: str,
        end_date: str,
        adjust: str
    ) -> pd.DataFrame:
        """使用akshare获取日线数据"""
        # 转换日期格式
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')
        
        df = self._safe_call(
            ak.stock_zh_a_hist, 
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )
        
        # 标准化列名
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '振幅': 'amplitude',
            '涨跌幅': 'pct_change',
            '涨跌额': 'change_amount',
            '换手率': 'turnover',
        }
        df = df.rename(columns=column_mapping)
        df['code'] = code
        
        # 转换日期格式
        df['date'] = pd.to_datetime(df['date'])
        
        return df
    
    def _get_daily_price_baostock(
        self, 
        code: str, 
        start_date: str,
        end_date: str,
        adjust: str
    ) -> pd.DataFrame:
        """使用baostock获取日线数据"""
        self._ensure_bs_login()
        
        # 转换日期格式 YYYYMMDD -> YYYY-MM-DD
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')
        
        # 转换日期格式 baostock需要 YYYY-MM-DD
        start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
        
        # 转换代码格式: 600000 -> sh.600000
        if code.startswith('6'):
            bs_code = f"sh.{code}"
        else:
            bs_code = f"sz.{code}"
        
        # 复权类型: 2=前复权, 1=后复权, 3=不复权
        adjust_flag = {'qfq': '2', 'hfq': '1', '': '3'}.get(adjust, '2')
        
        # 获取数据
        rs = bs.query_history_k_data_plus(
            bs_code,
            'date,code,open,high,low,close,volume,amount,turn',
            start_date=start_date,
            end_date=end_date,
            frequency='d',
            adjustflag=adjust_flag
        )
        
        if rs.error_code != '0':
            raise Exception(f"baostock获取数据失败: {rs.error_msg}")
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            return pd.DataFrame(columns=['date', 'code', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover'])
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 标准化列名
        df = df.rename(columns={
            'turn': 'turnover'
        })
        
        # 移除code列（baostock返回的带前缀的code）
        if 'code' in df.columns:
            df = df.drop(columns=['code'])
        
        # 添加code列
        df['code'] = code
        
        # 转换日期格式
        df['date'] = pd.to_datetime(df['date'])
        
        # 转换数值类型 - 先将'None'字符串替换为None
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turnover']
        for col in numeric_cols:
            if col in df.columns:
                # 将字符串'None'替换为Python的None
                df[col] = df[col].replace('None', None)
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 添加缺失的列（与akshare格式兼容，设置为None）
        if 'amplitude' not in df.columns:
            df['amplitude'] = None
        if 'pct_change' not in df.columns:
            df['pct_change'] = None
        if 'change_amount' not in df.columns:
            df['change_amount'] = None
        
        return df
    
    def _get_daily_price_tushare(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str
    ) -> pd.DataFrame:
        """使用tushare获取日线数据"""
        if not self._ensure_tushare_login():
            logger.warning("TUSHARE_TOKEN未设置或无效，使用akshare获取日线数据")
            return self._get_daily_price_akshare(code, start_date, end_date, adjust)
        
        tushare_limiter.acquire()
        
        ts_code = to_tushare(code)
        
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')
        
        if adjust and adjust != '':
            df = self._safe_call(
                ts.pro_bar, ts_code=ts_code, start_date=start_date, 
                end_date=end_date, adj=adjust, freq='D'
            )
        else:
            df = self._safe_call(
                self._tushare_pro.daily, ts_code=ts_code, 
                start_date=start_date, end_date=end_date
            )
        
        if df is None or df.empty:
            return pd.DataFrame(columns=['date', 'code', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover'])
        
        df = df.rename(columns={
            'trade_date': 'date',
            'vol': 'volume',
        })
        
        if 'ts_code' in df.columns:
            df = df.drop(columns=['ts_code'])
        
        df['code'] = code
        df['date'] = pd.to_datetime(df['date'])
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # ========== 单位转换 (tushare -> 数据库标准单位) ==========
        # tushare: volume单位是手(hand), amount单位是千元
        # 数据库: volume单位是股, amount单位是元
        # 转换: volume * 100, amount * 1000
        if 'volume' in df.columns:
            df['volume'] = df['volume'] * 100
        
        if 'amount' in df.columns:
            df['amount'] = df['amount'] * 1000
        # =========================================================
        
        if 'amplitude' not in df.columns:
            df['amplitude'] = None
        if 'pct_change' not in df.columns:
            df['pct_change'] = None
        if 'change_amount' not in df.columns:
            df['change_amount'] = None
        if 'turnover' not in df.columns:
            df['turnover'] = None
        
        return df
    
    # ==================== 批量获取 ====================
    
    def batch_get_daily_price(
        self,
        codes: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        progress_callback=None
    ) -> pd.DataFrame:
        """批量获取日线数据"""
        all_data = []
        total = len(codes)
        
        for i, code in enumerate(codes):
            try:
                df = self.get_daily_price(code, start_date, end_date)
                all_data.append(df)
                
                if progress_callback:
                    progress_callback(i + 1, total, code)
                else:
                    print(f"[{i+1}/{total}] 已获取 {code}")
                    
            except Exception as e:
                print(f"获取 {code} 失败: {e}")
                continue
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()


# 便捷函数：使用指定数据源创建Fetcher
def create_fetcher(source: str = None) -> StockFetcher:
    """创建StockFetcher实例"""
    return StockFetcher(source=source)

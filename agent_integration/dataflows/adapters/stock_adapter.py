"""
股票数据适配器 - StockDataAdapter实现
"""
import sys
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.db_manager import DatabaseManager
from data.fetchers.stock_fetcher import StockFetcher
from config.settings import Settings
from agent_integration.dataflows.markets.router import MarketRouter


class StockDataAdapter:
    """股票数据适配器
    
    将外部股票数据转换为统一格式，供智能体使用。
    优先从本地数据库获取，不足时从akshare补充。
    支持A股、港股、美股。
    """
    
    def __init__(self):
        """初始化股票数据适配器"""
        self._db = None
        # 优先使用akshare
        self.fetcher = StockFetcher('akshare')
        self.market_router = MarketRouter()
    
    @property
    def db(self):
        """延迟初始化数据库连接"""
        if self._db is None:
            try:
                self._db = DatabaseManager()
            except Exception as e:
                print(f"数据库连接失败: {e}")
                self._db = None
        return self._db
    
    def get_market_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取市场数据 (K线数据)
        
        优先从本地数据库获取，不足时从akshare补充。
        支持A股、港股、美股自动识别。
        
        Args:
            symbol: 股票代码，如 '600519', 'HK.00700', 'US.AAPL'
            start_date: 开始日期，格式 'YYYYMMDD' 或 'YYYY-MM-DD'
            end_date: 结束日期，格式 'YYYYMMDD' 或 'YYYY-MM-DD'
            
        Returns:
            DataFrame，包含 date, open, high, low, close, volume 等字段
        """
        # 标准化日期格式
        start_date = self._normalize_date(start_date)
        end_date = self._normalize_date(end_date)
        
        # 检测市场
        market = self.market_router.detect_market(symbol)
        
        # 港股和美股直接从市场路由获取
        if market in ['hk', 'us']:
            return self.market_router.get_market_data(symbol, start_date, end_date)
        
        # A股：先从本地数据库获取
        local_df = self._get_local_price(symbol, start_date, end_date)
        
        if local_df is not None and len(local_df) > 0:
            # 检查数据完整性
            local_count = len(local_df)
            
            # 尝试补充缺失数据
            if local_count < 10:
                # 数据太少，从akshare补充
                akshare_df = self._fetch_from_akshare(symbol, start_date, end_date)
                if akshare_df is not None and len(akshare_df) > 0:
                    return akshare_df
            
            return local_df
        
        # 本地无数据，从akshare获取
        akshare_df = self._fetch_from_akshare(symbol, start_date, end_date)
        
        if akshare_df is not None and len(akshare_df) > 0:
            # 保存到本地数据库
            if self.db is not None:
                try:
                    self.db.save_daily_price(akshare_df)
                except Exception as e:
                    print(f"保存数据到本地数据库失败: {e}")
        
        return akshare_df if akshare_df is not None else pd.DataFrame()
    
    def _get_local_price(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """从本地数据库获取价格数据"""
        if self.db is None:
            return None
        try:
            df = self.db.get_daily_price(symbol, start_date, end_date)
            if df is not None and len(df) > 0:
                return df
        except Exception as e:
            print(f"从本地数据库获取数据失败: {e}")
        return None
    
    def _fetch_from_akshare(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """从akshare获取价格数据"""
        try:
            df = self.fetcher.get_daily_price(symbol, start_date, end_date, adjust='qfq')
            if df is not None and len(df) > 0:
                return df
        except Exception as e:
            print(f"从akshare获取数据失败: {e}")
        return None
    
    def _normalize_date(self, date_str: str) -> str:
        """标准化日期格式"""
        if not date_str:
            return ''
        # 去除连字符
        date_str = date_str.replace('-', '')
        return date_str
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票基本信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票信息字典
        """
        # 先从本地数据库获取
        if self.db is not None:
            try:
                df = self.db.get_stock_info(symbol)
                if df is not None and len(df) > 0:
                    return self._parse_stock_info(df.iloc[0])
            except Exception:
                pass
        
        # 从akshare获取
        try:
            df = self.fetcher.get_stock_info(symbol)
            if df is not None and len(df) > 0:
                info = self._parse_stock_info(df.iloc[0])
                # 保存到本地
                if self.db is not None:
                    try:
                        df_save = pd.DataFrame([{
                            'code': symbol,
                            'name': info.get('name', ''),
                            'industry': info.get('industry', ''),
                            'market_cap': info.get('market_cap'),
                            'listing_date': info.get('listing_date'),
                        }])
                        self.db.save_stock_info(df_save)
                    except Exception:
                        pass
                return info
        except Exception as e:
            print(f"获取股票信息失败: {e}")
        
        return {}
    
    def _parse_stock_info(self, row: pd.Series) -> Dict[str, Any]:
        """解析股票信息"""
        info = {}
        
        # 尝试多种列名
        if 'code' in row.index:
            info['code'] = str(row['code'])
        if 'name' in row.index:
            info['name'] = str(row.get('name', ''))
        if 'industry' in row.index:
            info['industry'] = str(row.get('industry', ''))
        if 'market_cap' in row.index:
            info['market_cap'] = row.get('market_cap')
        if 'listing_date' in row.index:
            info['listing_date'] = str(row.get('listing_date', ''))
        
        # akshare股票信息详情格式
        if 'item' in row.index and 'value' in row.index:
            for idx, item in enumerate(row.get('item', [])):
                info[str(item).lower()] = row.get('value', [])[idx] if idx < len(row.get('value', [])) else None
        
        return info
    
    def get_fundamentals(self, symbol: str, period: str = 'quarter') -> Dict[str, Any]:
        """获取基本面数据
        
        使用tushare数据源获取股票基本面数据，包括盈利能力、成长能力和估值数据。
        
        Args:
            symbol: 股票代码，如 '600519'
            period: 财报周期 ('quarter' 或 'annual')
            
        Returns:
            基本面数据字典，包含 profitability、growth、valuation 三个维度
        """
        fundamentals = {}
        
        try:
            import tushare as ts
            from dotenv import load_dotenv
            
            load_dotenv()
            TUSHARE_TOKEN = os.getenv('TUSHARE_TOKEN')
            
            if not TUSHARE_TOKEN:
                print("TUSHARE_TOKEN未设置，无法获取基本面数据")
                return fundamentals
            
            # 初始化tushare
            pro = ts.pro_api(TUSHARE_TOKEN)
            
            # 转换股票代码格式 (tushare格式: 600519.SH)
            ts_symbol = self._convert_to_tushare_symbol(symbol)
            
            # 获取盈利能力数据 (使用fina_indicator接口)
            try:
                profit_df = pro.fina_indicator(ts_code=ts_symbol, limit=1)
                if profit_df is not None and len(profit_df) > 0:
                    latest = profit_df.iloc[0].to_dict()
                    fundamentals['profitability'] = {
                        '净利润': latest.get('q_profit', latest.get('profit_dedt', '')),
                        '营业总收入': latest.get('q_sales', latest.get('total_revenue', '')),
                        '营业总成本': latest.get('q_op_cost', latest.get('total_cogs', '')),
                        '基本每股收益': latest.get('eps', ''),
                        '净资产收益率': latest.get('roe', ''),
                        '净资产收益率(扣非)': latest.get('roe_deducted', ''),
                        '毛利率': latest.get('grossprofit_margin', ''),
                        '净利率': latest.get('netprofit_margin', ''),
                        '营业利润率': latest.get('op_of_gr', ''),
                    }
            except Exception as e:
                print(f"获取盈利能力数据失败: {e}")
            
            # 获取成长能力数据 (使用fina_indicator接口中的增长率指标)
            try:
                if profit_df is not None and len(profit_df) > 0:
                    latest = profit_df.iloc[0].to_dict()
                    fundamentals['growth'] = {
                        '净利润同比增长率': latest.get('q_profit_yoy', ''),
                        '扣非净利润同比增长率': latest.get('profit_dedt_yoy', ''),
                        '营业总收入同比增长率': latest.get('q_sales_yoy', ''),
                        '基本每股收益同比增长率': latest.get('basic_eps_yoy', ''),
                        '净资产收益率同比增长': latest.get('roe_yoy', ''),
                        '营业收入环比增长率': latest.get('or_yoy', ''),
                    }
            except Exception as e:
                print(f"获取成长能力数据失败: {e}")
            
            # 获取估值数据 (使用daily_basic接口)
            try:
                # 获取最新交易日的估值数据
                valuation_df = pro.daily_basic(ts_code=ts_symbol, limit=1)
                if valuation_df is not None and len(valuation_df) > 0:
                    latest = valuation_df.iloc[0].to_dict()
                    fundamentals['valuation'] = {
                        '总市值': latest.get('total_mv', ''),
                        '流通市值': latest.get('circ_mv', ''),
                        '市盈率(PE)': latest.get('pe', ''),
                        '市盈率(TTM)': latest.get('pe_ttm', ''),
                        '市净率(PB)': latest.get('pb', ''),
                        '市销率(PS)': latest.get('ps', ''),
                        '市销率(TTM)': latest.get('ps_ttm', ''),
                        '股息率': latest.get('dv_ratio', ''),
                        '换手率': latest.get('turnover_rate', ''),
                    }
            except Exception as e:
                print(f"获取估值数据失败: {e}")
            
            # 获取股票基本信息 (使用stock_basic接口)
            try:
                basic_df = pro.stock_basic(ts_code=ts_symbol)
                if basic_df is not None and len(basic_df) > 0:
                    basic = basic_df.iloc[0].to_dict()
                    fundamentals['basic_info'] = {
                        '股票名称': basic.get('name', ''),
                        '行业': basic.get('industry', ''),
                        '所属行业': basic.get('industry', ''),
                        '地区': basic.get('area', ''),
                        '市场': basic.get('market', ''),
                        '上市日期': basic.get('list_date', ''),
                    }
            except Exception as e:
                print(f"获取基本信息失败: {e}")
            
        except ImportError:
            print("tushare未安装，无法获取基本面数据")
        except Exception as e:
            print(f"获取基本面数据失败: {e}")
        
        return fundamentals
    
    def _convert_to_tushare_symbol(self, symbol: str) -> str:
        """将股票代码转换为tushare格式
        
        Args:
            symbol: 原始股票代码，如 '600519', '000001'
            
        Returns:
            tushare格式的股票代码，如 '600519.SH', '000001.SZ'
        """
        symbol = str(symbol).strip()
        
        # 如果已经是tushare格式，直接返回
        if '.' in symbol:
            return symbol
        
        # 根据代码前缀判断交易所
        if symbol.startswith('6'):
            return f"{symbol}.SH"  # 上海证券交易所
        elif symbol.startswith('0') or symbol.startswith('3'):
            return f"{symbol}.SZ"  # 深圳证券交易所
        elif symbol.startswith('68'):
            return f"{symbol}.SH"  # 科创板
        elif symbol.startswith('8') or symbol.startswith('4'):
            return f"{symbol}.BJ"  # 北交所
        else:
            # 默认使用深圳交易所
            return f"{symbol}.SZ"
    
    def _clean_financial_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清理财务数据"""
        cleaned = {}
        for key, value in data.items():
            if value is None or str(value) == 'None' or str(value) == '-':
                continue
            try:
                # 尝试转换为数值
                cleaned[str(key)] = float(value)
            except (ValueError, TypeError):
                cleaned[str(key)] = str(value)
        return cleaned
    
    def adapt_price_data(self, raw_data: pd.DataFrame) -> Dict[str, Any]:
        """转换价格数据
        
        Args:
            raw_data: 原始价格数据
            
        Returns:
            标准化价格数据
        """
        if raw_data is None or len(raw_data) == 0:
            return {}
        
        latest = raw_data.iloc[-1]
        previous = raw_data.iloc[-2] if len(raw_data) > 1 else latest
        
        return {
            'code': str(latest.get('code', '')),
            'date': str(latest.get('date', '')),
            'open': float(latest.get('open', 0)),
            'high': float(latest.get('high', 0)),
            'low': float(latest.get('low', 0)),
            'close': float(latest.get('close', 0)),
            'volume': float(latest.get('volume', 0)),
            'pct_change': float(latest.get('pct_change', 0)),
            'change': float(latest.get('close', 0)) - float(previous.get('close', 0)) if len(raw_data) > 1 else 0,
        }
    
    def adapt_financial_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """转换财务数据
        
        Args:
            raw_data: 原始财务数据
            
        Returns:
            标准化财务数据
        """
        if not raw_data:
            return {}
        
        return {
            'data': raw_data,
            'update_time': datetime.now().isoformat(),
        }
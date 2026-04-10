"""
市场路由器 - MarketRouter
"""
import pandas as pd
from typing import Dict, Any, Literal

from .hk_stocks import HKStockData
from .us_stocks import USStockData


class MarketRouter:
    """市场路由器
    
    根据股票代码自动识别市场并路由到对应的数据源。
    
    Symbol格式约定:
    - A股: '600519', '000001', '300750', '688001', '430001'
    - 港股: '00700', '09988', 'HK.00700'
    - 美股: 'AAPL', 'GOOGL', 'US.AAPL', 'US.GOOGL'
    """
    
    CHINA_PATTERNS = ['^[SHsh]{2}\\d{6}$', '^\\d{6}$']
    HK_PATTERNS = ['^HK\\.', '^\\d{5}$', '^\\d{4}$']
    US_PATTERNS = ['^US\\.', '^[A-Z]{1,5}$', '^\\^[A-Z]']
    
    def __init__(self):
        self._hk_data = None
        self._us_data = None
    
    @property
    def hk_data(self) -> HKStockData:
        if self._hk_data is None:
            self._hk_data = HKStockData()
        return self._hk_data
    
    @property
    def us_data(self) -> USStockData:
        if self._us_data is None:
            self._us_data = USStockData()
        return self._us_data
    
    def detect_market(self, symbol: str) -> Literal['china', 'hk', 'us']:
        """自动识别市场
        
        Args:
            symbol: 股票代码
            
        Returns:
            'china', 'hk', 或 'us'
        """
        symbol = symbol.strip().upper()
        
        # 1. 前缀标记优先
        if symbol.startswith('HK.'):
            return 'hk'
        if symbol.startswith('US.'):
            return 'us'
        
        # 2. A股: 6/0/3/4/8开头 + 6位数字 (但排除纯数字4-5位如00700)
        if symbol.startswith(('6', '3', '4', '8')) and len(symbol) == 6:
            return 'china'
        if symbol.startswith('0') and len(symbol) == 6:
            return 'china'
        
        # 3. 港股: HK.前缀 或 4-5位纯数字 (如00700, 09988)
        if len(symbol) == 5 and symbol.isdigit():
            return 'hk'
        if len(symbol) == 4 and symbol.isdigit():
            return 'hk'
        
        # 4. 美股: 全大写字母，1-5位 (如AAPL, GOOG)
        if symbol.isupper() and len(symbol) <= 5 and symbol.isalpha():
            return 'us'
        
        # 5. 默认根据长度推测
        if len(symbol) == 6 and symbol.isdigit():
            return 'china'
        
        return 'us'
    
    def get_market_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = 'qfq'
    ) -> pd.DataFrame:
        """获取市场数据 (统一接口)
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 'YYYYMMDD'
            end_date: 结束日期 'YYYYMMDD'
            adjust: 复权类型
            
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        market = self.detect_market(symbol)
        
        if market == 'hk':
            return self.hk_data.get_historical_data(symbol, start_date, end_date, adjust)
        elif market == 'us':
            return self.us_data.get_historical_data(symbol, start_date, end_date, adjust)
        else:
            return pd.DataFrame()
    
    def get_realtime_data(self, symbol: str) -> Dict[str, Any]:
        """获取实时数据 (统一接口)
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时数据字典
        """
        market = self.detect_market(symbol)
        
        if market == 'hk':
            return self.hk_data.get_realtime_data(symbol)
        elif market == 'us':
            return self.us_data.get_realtime_data(symbol)
        else:
            return {}
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票信息 (统一接口)
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票信息字典
        """
        market = self.detect_market(symbol)
        
        if market == 'hk':
            return self.hk_data.get_stock_info(symbol)
        elif market == 'us':
            return self.us_data.get_stock_info(symbol)
        else:
            return {}
    
    def search_stocks(self, keyword: str, market: str = None) -> list:
        """搜索股票
        
        Args:
            keyword: 搜索关键词
            market: 市场过滤 ('china', 'hk', 'us', None表示全部)
            
        Returns:
            匹配的股票列表
        """
        if market is None or market == 'hk':
            hk_results = self.hk_data.search_stocks(keyword)
        else:
            hk_results = []
        
        if market is None or market == 'us':
            us_results = self.us_data.search_stocks(keyword)
        else:
            us_results = []
        
        return hk_results + us_results
    
    def get_data_source_name(self, market: str) -> str:
        """获取数据源名称
        
        Args:
            market: 市场标识
            
        Returns:
            数据源名称
        """
        names = {
            'china': '沪深市场',
            'hk': '港股',
            'us': '美股'
        }
        return names.get(market, '未知')
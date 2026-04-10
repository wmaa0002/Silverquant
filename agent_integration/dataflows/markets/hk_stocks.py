"""
港股数据源 - HKStockData
"""
import akshare as ak
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime


class HKStockData:
    """港股数据源
    
    获取港股历史数据和实时数据。
    Symbol格式: '00700' (腾讯), '09988' (阿里), 'HK.00700'
    """
    
    def __init__(self):
        self.name = '港股'
    
    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = 'qfq'
    ) -> pd.DataFrame:
        """获取港股历史数据
        
        Args:
            symbol: 股票代码，如 '00700' 或 'HK.00700'
            start_date: 开始日期 'YYYYMMDD'
            end_date: 结束日期 'YYYYMMDD'
            adjust: 复权类型 ('qfq', 'hfq', '')
            
        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount
        """
        clean_symbol = self._normalize_symbol(symbol)
        
        try:
            df = ak.stock_hk_hist(
                symbol=clean_symbol,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            df = self._standardize_columns(df)
            return df
            
        except Exception as e:
            print(f"获取港股历史数据失败: {e}")
            return pd.DataFrame()
    
    def get_realtime_data(self, symbol: str) -> Dict[str, Any]:
        """获取港股实时数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时数据字典
        """
        clean_symbol = self._normalize_symbol(symbol)
        
        try:
            df = ak.stock_hk_spot_em()
            
            if df is None or df.empty:
                return {}
            
            row = df[df['代码'] == clean_symbol]
            if row.empty:
                return {}
            
            return self._parse_realtime_row(row.iloc[0])
            
        except Exception as e:
            print(f"获取港股实时数据失败: {e}")
            return {}
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """获取港股基本信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票信息字典
        """
        clean_symbol = self._normalize_symbol(symbol)
        
        try:
            df = ak.stock_hk_spot_em()
            
            if df is None or df.empty:
                return {}
            
            row = df[df['代码'] == clean_symbol]
            if row.empty:
                return {}
            
            return self._parse_stock_info(row.iloc[0])
            
        except Exception as e:
            print(f"获取港股信息失败: {e}")
            return {}
    
    def search_stocks(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索港股
        
        Args:
            keyword: 搜索关键词（代码或名称）
            
        Returns:
            匹配的股票列表
        """
        try:
            df = ak.stock_hk_spot_em()
            
            if df is None or df.empty:
                return []
            
            keyword_upper = keyword.upper()
            mask = df['代码'].str.contains(keyword_upper, na=False) | \
                   df['名称'].str.contains(keyword, na=False)
            
            results = []
            for _, row in df[mask].head(20).iterrows():
                results.append({
                    'code': row['代码'],
                    'name': row['名称'],
                    'price': row.get('最新价', 0),
                    'change_pct': row.get('涨跌幅', 0),
                })
            
            return results
            
        except Exception as e:
            print(f"搜索港股失败: {e}")
            return []
    
    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码
        
        Args:
            symbol: 输入代码，如 'HK.00700' 或 '00700'
            
        Returns:
            标准化代码，如 '00700'
        """
        symbol = symbol.upper().strip()
        if symbol.startswith('HK.'):
            symbol = symbol[3:]
        return symbol
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名"""
        column_mapping = {
            '日期': 'date',
            '股票代码': 'code',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '涨跌幅': 'pct_change',
            '涨跌额': 'change',
            '换手率': 'turnover',
        }
        
        df = df.rename(columns=column_mapping)
        
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        
        return df
    
    def _parse_realtime_row(self, row: pd.Series) -> Dict[str, Any]:
        """解析实时数据行"""
        return {
            'code': row.get('代码', ''),
            'name': row.get('名称', ''),
            'price': row.get('最新价', 0),
            'change': row.get('涨跌额', 0),
            'change_pct': row.get('涨跌幅', 0),
            'volume': row.get('成交量', 0),
            'amount': row.get('成交额', 0),
            'open': row.get('今开', row.get('开盘', 0)),
            'high': row.get('最高', 0),
            'low': row.get('最低', 0),
            'prev_close': row.get('昨收', row.get('收盘', 0)),
            'timestamp': datetime.now().isoformat()
        }
    
    def _parse_stock_info(self, row: pd.Series) -> Dict[str, Any]:
        """解析股票信息"""
        return {
            'code': row.get('代码', ''),
            'name': row.get('名称', ''),
            'price': row.get('最新价', 0),
            'change_pct': row.get('涨跌幅', 0),
            'market_cap': row.get('总市值', 0),
            'pe': row.get('市盈率', 0),
            'dividend_yield': row.get('股息率', 0),
        }
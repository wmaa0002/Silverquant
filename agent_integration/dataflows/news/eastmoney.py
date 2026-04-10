"""
东方财富新闻源 - EastMoneyNews实现
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional

from agent_integration.dataflows.news.base import BaseNewsSource, NewsItem


class EastMoneyNews(BaseNewsSource):
    """东方财富新闻源
    
    从东方财富网获取新闻数据。
    """
    
    def __init__(self):
        """初始化东方财富新闻源"""
        super().__init__('东方财富')
    
    def get_stock_news(self, symbol: str, limit: int = 20,
                       start_date: Optional[str] = None) -> List[NewsItem]:
        """获取个股新闻
        
        Args:
            symbol: 股票代码，如 '600519'
            limit: 返回数量限制
            start_date: 开始日期，格式 'YYYYMMDD' 或 'YYYY-MM-DD' (可选)
            
        Returns:
            NewsItem列表
        """
        try:
            df = ak.stock_news_em(symbol=symbol)
            
            if df is None or df.empty:
                return []
            
            news_items = []
            for _, row in df.iterrows():
                published_at = row.get('发布时间', '')
                
                news_item = NewsItem(
                    title=str(row.get('新闻标题', '')),
                    content=str(row.get('新闻内容', '')),
                    published_at=published_at,
                    source=str(row.get('文章来源', self.name)),
                    url=str(row.get('新闻链接', '')) if pd.notna(row.get('新闻链接')) else None,
                    stock_codes=[symbol],
                    keywords=[str(row.get('关键词', ''))] if pd.notna(row.get('关键词')) else [],
                )
                news_items.append(news_item)
            
            # 按时间排序（最新的在前）
            news_items.sort(key=lambda x: x.published_at, reverse=True)
            
            # 应用日期过滤
            if start_date:
                start_dt = self._parse_date(start_date)
                news_items = [n for n in news_items if n.published_at >= start_dt]
            
            # 应用数量限制
            return news_items[:limit]
            
        except Exception as e:
            print(f"获取东方财富新闻失败: {e}")
            return []
    
    def get_market_news(self, market: str = 'cn', limit: int = 20,
                        start_date: Optional[str] = None) -> List[NewsItem]:
        """获取市场新闻
        
        目前东方财富API主要支持个股新闻，市场新闻暂用A股大盘新闻替代。
        
        Args:
            market: 市场标识 (暂未使用，保留接口)
            limit: 返回数量限制
            start_date: 开始日期
            
        Returns:
            NewsItem列表
        """
        # 东方财富市场新闻API (暂时使用重要新闻)
        try:
            df = ak.stock_news_em(symbol='000001')  # 使用上证指数作为市场代表
            
            if df is None or df.empty:
                return []
            
            news_items = []
            for _, row in df.iterrows():
                published_at = row.get('发布时间', '')
                
                news_item = NewsItem(
                    title=str(row.get('新闻标题', '')),
                    content=str(row.get('新闻内容', '')),
                    published_at=published_at,
                    source=str(row.get('文章来源', self.name)),
                    url=str(row.get('新闻链接', '')) if pd.notna(row.get('新闻链接')) else None,
                    keywords=[str(row.get('关键词', ''))] if pd.notna(row.get('关键词')) else [],
                )
                news_items.append(news_item)
            
            # 按时间排序
            news_items.sort(key=lambda x: x.published_at, reverse=True)
            
            # 应用日期过滤
            if start_date:
                start_dt = self._parse_date(start_date)
                news_items = [n for n in news_items if n.published_at >= start_dt]
            
            return news_items[:limit]
            
        except Exception as e:
            print(f"获取市场新闻失败: {e}")
            return []
    
    def fetch_news(self, keyword: str, days: int = 7) -> List[NewsItem]:
        """获取新闻
        
        Args:
            keyword: 搜索关键词（股票代码）
            days: 获取最近天数
            
        Returns:
            新闻列表
        """
        return self.get_stock_news(symbol=keyword, limit=100)
    
    def parse_news_item(self, raw_data: dict) -> NewsItem:
        """解析东方财富原始数据
        
        Args:
            raw_data: 东方财富原始数据字典
            
        Returns:
            NewsItem对象
        """
        return NewsItem(
            title=str(raw_data.get('新闻标题', raw_data.get('title', ''))),
            content=str(raw_data.get('新闻内容', raw_data.get('content', ''))),
            published_at=raw_data.get('发布时间', raw_data.get('published_at', datetime.now())),
            source=str(raw_data.get('文章来源', raw_data.get('source', self.name))),
            url=str(raw_data.get('新闻链接', raw_data.get('url', ''))) if raw_data.get('新闻链接') else None,
            keywords=[str(raw_data.get('关键词', ''))] if raw_data.get('关键词') else [],
        )
    
    def _parse_date(self, date_str: str) -> datetime:
        """解析日期字符串
        
        Args:
            date_str: 日期字符串，格式 'YYYYMMDD' 或 'YYYY-MM-DD'
            
        Returns:
            datetime对象
        """
        if not date_str:
            return datetime.now() - timedelta(days=7)
        
        # 去除连字符
        date_str = date_str.replace('-', '')
        
        if len(date_str) == 8:
            return datetime.strptime(date_str, '%Y%m%d')
        
        return datetime.strptime(date_str[:10], '%Y-%m-%d')
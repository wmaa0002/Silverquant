"""
新闻数据基础类 - NewsItem, Sentiment, BaseNewsSource
"""
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod


class Sentiment(Enum):
    """情感枚举"""
    POSITIVE = 'positive'
    NEGATIVE = 'negative'
    NEUTRAL = 'neutral'


@dataclass
class NewsItem:
    """
    新闻数据类
    
    Attributes:
        title: 新闻标题
        content: 新闻内容
        published_at: 发布时间 (datetime类型，兼容多种格式)
        source: 来源
        url: 链接
        sentiment: 情感分类
        stock_codes: 关联股票代码列表
        keywords: 关键词列表
    """
    title: str
    content: str
    published_at: datetime
    source: str
    url: Optional[str] = None
    sentiment: Optional[Sentiment] = None
    stock_codes: Optional[List[str]] = field(default_factory=list)
    keywords: Optional[List[str]] = field(default_factory=list)
    
    def __post_init__(self):
        """后处理，确保published_at是datetime类型"""
        if isinstance(self.published_at, str):
            # 尝试多种日期格式
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d',
                '%Y%m%d %H:%M:%S',
            ]
            for fmt in formats:
                try:
                    self.published_at = datetime.strptime(self.published_at, fmt)
                    break
                except ValueError:
                    continue
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'title': self.title,
            'content': self.content,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'source': self.source,
            'url': self.url,
            'sentiment': self.sentiment.value if self.sentiment else None,
            'stock_codes': self.stock_codes,
            'keywords': self.keywords,
        }


class BaseNewsSource(ABC):
    """
    新闻源基类
    
    定义新闻获取接口，所有新闻源需继承此类。
    """
    
    def __init__(self, name: str):
        """
        初始化新闻源
        
        Args:
            name: 新闻源名称
        """
        self.name = name
    
    @abstractmethod
    def get_stock_news(self, symbol: str, limit: int = 20, 
                       start_date: Optional[str] = None) -> List[NewsItem]:
        """
        获取个股新闻
        
        Args:
            symbol: 股票代码，如 '600519'
            limit: 返回数量限制
            start_date: 开始日期，格式 'YYYYMMDD' 或 'YYYY-MM-DD'
            
        Returns:
            NewsItem列表
        """
        pass
    
    @abstractmethod
    def get_market_news(self, market: str, limit: int = 20,
                        start_date: Optional[str] = None) -> List[NewsItem]:
        """
        获取市场新闻
        
        Args:
            market: 市场标识，如 'cn' (中国A股), 'hk' (港股), 'us' (美股)
            limit: 返回数量限制
            start_date: 开始日期，格式 'YYYYMMDD' 或 'YYYY-MM-DD'
            
        Returns:
            NewsItem列表
        """
        pass
    
    def fetch_news(self, keyword: str, days: int = 7) -> List[NewsItem]:
        """
        获取新闻 (通用方法，子类可覆盖)
        
        Args:
            keyword: 搜索关键词
            days: 获取最近天数
            
        Returns:
            新闻列表
        """
        # 默认实现调用get_stock_news
        return self.get_stock_news(symbol=keyword, limit=100)
    
    def parse_news_item(self, raw_data: Dict[str, Any]) -> NewsItem:
        """
        解析原始新闻数据为NewsItem (子类需覆盖)
        
        Args:
            raw_data: 原始数据字典
            
        Returns:
            NewsItem对象
        """
        return NewsItem(
            title=raw_data.get('title', ''),
            content=raw_data.get('content', ''),
            published_at=raw_data.get('published_at', datetime.now()),
            source=raw_data.get('source', self.name),
            url=raw_data.get('url'),
            stock_codes=raw_data.get('stock_codes', []),
            keywords=raw_data.get('keywords', []),
        )
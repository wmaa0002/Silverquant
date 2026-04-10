"""
新闻聚合器 - NewsAggregator实现
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent_integration.dataflows.news.base import BaseNewsSource, NewsItem, Sentiment
from agent_integration.dataflows.news.eastmoney import EastMoneyNews


@dataclass
class StockNewsResult:
    """股票新闻结果"""
    stock_code: str
    news_list: List[NewsItem]
    total_count: int
    sources_used: List[str]
    
    def __post_init__(self):
        if self.total_count == 0:
            self.total_count = len(self.news_list)


class NewsAggregator:
    """新闻聚合器
    
    从多个新闻源聚合新闻数据并进行统一处理。
    默认使用东方财富作为新闻源。
    支持A股、港股、美股新闻。
    """
    
    DEFAULT_SOURCES = ['eastmoney']
    
    def __init__(self, sources: Optional[List[str]] = None):
        """初始化新闻聚合器
        
        Args:
            sources: 新闻源名称列表，如 ['eastmoney']
        """
        self.source_names = sources or self.DEFAULT_SOURCES
        self._sources: Dict[str, BaseNewsSource] = {}
        self._init_sources()
    
    def _init_sources(self):
        """初始化新闻源实例"""
        for source_name in self.source_names:
            if source_name == 'eastmoney':
                self._sources[source_name] = EastMoneyNews()
    
    def _detect_market_for_news(self, symbol: str) -> str:
        """检测适合的新闻市场
        
        Args:
            symbol: 股票代码
            
        Returns:
            'china', 'hk', 'us'
        """
        symbol = symbol.upper().strip()
        
        if symbol.startswith('HK.'):
            return 'hk'
        if symbol.startswith('US.'):
            return 'us'
        
        if symbol.startswith('6') or symbol.startswith('0') or \
           symbol.startswith('3') or symbol.startswith('4') or \
           symbol.startswith('8') or symbol.isdigit():
            return 'china'
        
        if len(symbol) == 5 or len(symbol) == 4:
            return 'hk'
        
        if symbol.isupper() and len(symbol) <= 5 and symbol.isalpha():
            return 'us'
        
        return 'china'
    
    def get_stock_news(self, symbol: str, sources: Optional[List[str]] = None,
                      limit: int = 20, include_sentiment: bool = True) -> StockNewsResult:
        """获取个股新闻 (并行调用多个新闻源)
        
        Args:
            symbol: 股票代码，支持A股(600519)、港股(HK.00700)、美股(US.AAPL)
            sources: 使用的新闻源列表，None表示使用默认源
            limit: 返回数量限制
            include_sentiment: 是否进行情感分析
            
        Returns:
            StockNewsResult对象
        """
        # 检测市场
        market = self._detect_market_for_news(symbol)
        
        # 港股和美股暂时返回空结果（需要额外的新闻源支持）
        if market in ['hk', 'us']:
            return StockNewsResult(
                stock_code=symbol,
                news_list=[],
                total_count=0,
                sources_used=[],
            )
        
        use_sources = sources or self.source_names
        all_news: List[NewsItem] = []
        sources_used = []
        
        # 并行获取各新闻源数据
        with ThreadPoolExecutor(max_workers=len(use_sources)) as executor:
            future_to_source = {}
            for source_name in use_sources:
                if source_name in self._sources:
                    source = self._sources[source_name]
                    future = executor.submit(source.get_stock_news, symbol, limit * 2)
                    future_to_source[future] = source_name
            
            for future in as_completed(future_to_source):
                source_name = future_to_source[future]
                try:
                    news_list = future.result()
                    if news_list:
                        all_news.extend(news_list)
                        sources_used.append(source_name)
                except Exception as e:
                    print(f"新闻源 {source_name} 获取失败: {e}")
        
        # 去重
        all_news = self.deduplicate(all_news)
        
        # 按时间排序
        all_news.sort(key=lambda x: x.published_at, reverse=True)
        
        # 限制数量
        all_news = all_news[:limit]
        
        return StockNewsResult(
            stock_code=symbol,
            news_list=all_news,
            total_count=len(all_news),
            sources_used=sources_used,
        )
    
    def get_market_news(self, market: str = 'cn', limit: int = 20) -> List[NewsItem]:
        """获取市场新闻
        
        Args:
            market: 市场标识
            limit: 返回数量限制
            
        Returns:
            市场新闻列表
        """
        all_news: List[NewsItem] = []
        
        for source_name, source in self._sources.items():
            try:
                news_list = source.get_market_news(market, limit)
                all_news.extend(news_list)
            except Exception as e:
                print(f"新闻源 {source_name} 获取市场新闻失败: {e}")
        
        # 去重
        all_news = self.deduplicate(all_news)
        
        # 按时间排序
        all_news.sort(key=lambda x: x.published_at, reverse=True)
        
        return all_news[:limit]
    
    def deduplicate(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """按URL去重
        
        Args:
            news_list: 新闻列表
            
        Returns:
            去重后的新闻列表
        """
        seen_urls = set()
        unique_news = []
        
        for news in news_list:
            if news.url and news.url not in seen_urls:
                seen_urls.add(news.url)
                unique_news.append(news)
            elif not news.url:
                # 没有URL的新闻直接保留
                unique_news.append(news)
        
        return unique_news
    
    def add_source(self, source: BaseNewsSource):
        """添加新闻源
        
        Args:
            source: 新闻源实例
        """
        self._sources[source.name] = source
        if source.name not in self.source_names:
            self.source_names.append(source.name)
    
    def aggregate(self, keyword: str, days: int = 7) -> List[NewsItem]:
        """聚合多源新闻
        
        Args:
            keyword: 搜索关键词
            days: 获取最近天数
            
        Returns:
            聚合后的新闻列表
        """
        all_news: List[NewsItem] = []
        
        for source in self._sources.values():
            try:
                news_list = source.fetch_news(keyword, days)
                all_news.extend(news_list)
            except Exception as e:
                print(f"新闻源 {source.name} 获取失败: {e}")
        
        all_news = self.deduplicate(all_news)
        all_news.sort(key=lambda x: x.published_at, reverse=True)
        
        return all_news
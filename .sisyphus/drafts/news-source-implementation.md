# 新闻源详细实现方案

> **生成时间**: 2026-03-29
> **模块**: agent_integration/dataflows/news/

---

## 1. 新闻源概览

### 1.1 支持的新闻源

| 来源 | 类型 | 语言 | 实时性 | API Key | 实现难度 |
|------|------|------|--------|---------|----------|
| **东方财富** | Web Scraping | 中文 | 实时 | 不需要 | ⭐⭐ |
| **财新** | RSS | 中文 | 小时级 | 不需要 | ⭐ |
| **新浪财经** | Web Scraping | 中文 | 实时 | 不需要 | ⭐⭐ |
| **Google News** | Search API | 多语言 | 实时 | 不需要 | ⭐⭐⭐ |
| **FinnHub** | REST API | 英文 | 实时 | 需要 | ⭐ |
| **Alpha Vantage** | REST API | 英文 | 实时 | 需要 | ⭐ |

### 1.2 新闻数据结构

```python
# agent_integration/dataflows/news/schema.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class Sentiment(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

@dataclass
class NewsItem:
    """新闻条目"""
    title: str                    # 标题
    content: str                  # 内容摘要 (前200字)
    source: str                   # 来源标识 (e.g., 'eastmoney', 'sina')
    url: str                      # 原文链接
    published_at: datetime        # 发布时间
    
    # 关联信息
    symbols: List[str] = field(default_factory=list)  # 关联股票代码
    keywords: List[str] = field(default_factory=list)  # 关键词
    
    # 情感分析
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_score: float = 0.0  # -1.0 ~ 1.0
    
    # 元数据
   爬取时间: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'content': self.content,
            'source': self.source,
            'url': self.url,
            'published_at': self.published_at.isoformat(),
            'symbols': self.symbols,
            'sentiment': self.sentiment.value,
            'sentiment_score': self.sentiment_score,
        }

@dataclass
class StockNewsResult:
    """股票新闻结果"""
    symbol: str
    news: List[NewsItem]
    total_count: int
    fetched_at: datetime
    sources: List[str]  # 实际使用的来源
```

---

## 2. 基类设计

### 2.1 新闻源基类

```python
# agent_integration/dataflows/news/base.py

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class BaseNewsSource(ABC):
    """新闻源基类"""
    
    name: str  # 来源标识
    base_url: str  # 基础URL
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
    
    @abstractmethod
    def get_stock_news(
        self, 
        symbol: str, 
        limit: int = 20,
        start_date: Optional[datetime] = None
    ) -> List[NewsItem]:
        """
        获取指定股票的新闻
        
        Args:
            symbol: 股票代码 (e.g., '600519', '000001')
            limit: 返回数量
            start_date: 开始日期 (默认最近7天)
            
        Returns:
            List[NewsItem]: 新闻列表
        """
        pass
    
    @abstractmethod
    def get_market_news(
        self, 
        market: str = 'china',
        limit: int = 20,
        start_date: Optional[datetime] = None
    ) -> List[NewsItem]:
        """
        获取市场整体新闻
        
        Args:
            market: 市场 ('china', 'hk', 'us')
            limit: 返回数量
            start_date: 开始日期
            
        Returns:
            List[NewsItem]: 新闻列表
        """
        pass
    
    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        # 子类可覆盖实现特定格式
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%Y/%m/%d %H:%M:%S',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    
    def _clean_html(self, text: str) -> str:
        """清理HTML标签"""
        import re
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
```

---

## 3. 东方财富新闻源

### 3.1 接口分析

**搜索接口**:
```
URL: https://search-api-web.eastmoney.com/search/jsonp
Method: GET
Params:
  - uid: (随机)
  - keyword: 股票代码/名称
  - type: [14] (新闻类型)
  - page: 1
  - pagesize: 20
  - id: (时间戳)
  - name: (随机)
```

**实时新闻接口**:
```
URL: https://np-anotice-stock.eastmoney.com/api/security/ann
Method: GET
Params:
  - sr=-1&page_size=20&page_index=1&ann_type=SHA%2CCYB%2CSZA
  - stock_list: 600519 (股票代码)
```

### 3.2 实现代码

```python
# agent_integration/dataflows/news/eastmoney.py

import requests
import json
import random
import time
from typing import List, Optional
from datetime import datetime, timedelta
from .base import BaseNewsSource, NewsItem, Sentiment

class EastMoneyNews(BaseNewsSource):
    """东方财富新闻源"""
    
    name = 'eastmoney'
    base_url = 'https://search-api-web.eastmoney.com'
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://so.eastmoney.com/',
        })
    
    def get_stock_news(
        self, 
        symbol: str, 
        limit: int = 20,
        start_date: Optional[datetime] = None
    ) -> List[NewsItem]:
        """
        获取东方财富新闻
        """
        news_list = []
        
        # 方法1: 搜索接口
        search_news = self._search_news(symbol, limit)
        news_list.extend(search_news)
        
        # 方法2: 公告接口 (更权威)
        announcement_news = self._get_announcements(symbol, limit)
        news_list.extend(announcement_news)
        
        # 去重
        seen = set()
        unique_news = []
        for item in news_list:
            if item.url not in seen:
                seen.add(item.url)
                unique_news.append(item)
        
        # 按时间排序
        unique_news.sort(key=lambda x: x.published_at, reverse=True)
        
        # 过滤日期
        if start_date:
            unique_news = [n for n in unique_news if n.published_at >= start_date]
        
        return unique_news[:limit]
    
    def _search_news(self, keyword: str, limit: int) -> List[NewsItem]:
        """搜索新闻"""
        news_list = []
        
        try:
            # 生成随机参数
            uid = random.randint(100000000, 999999999)
            ts = int(time.time() * 1000)
            
            params = {
                'uid': str(uid),
                'keyword': keyword,
                'type': '[14]',  # 新闻
                'page': 1,
                'pagesize': limit,
                'id': str(ts),
                'name': f'page_{random.randint(1000, 9999)}',
            }
            
            url = f"{self.base_url}/search/jsonp"
            response = self.session.get(url, params=params, timeout=10)
            
            # 解析JSONP回调
            text = response.text
            if text.startswith('jsonpCallback('):
                text = text[len('jsonpCallback('):-1]
            
            data = json.loads(text)
            result = data.get('result', {})
            hits = result.get('hits', [])
            
            for hit in hits:
                try:
                    title = hit.get('title', '')
                    content = hit.get('middle_content', '')[:200]
                    url = hit.get('url', '')
                    publish_time = hit.get('post_time', '')
                    
                    if not title or not url:
                        continue
                    
                    published_at = self._parse_datetime(publish_time)
                    if not published_at:
                        published_at = datetime.now()
                    
                    news_item = NewsItem(
                        title=self._clean_html(title),
                        content=self._clean_html(content),
                        source=self.name,
                        url=url,
                        published_at=published_at,
                    )
                    news_list.append(news_item)
                    
                except Exception as e:
                    self.logger.warning(f"解析新闻条目失败: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"搜索新闻失败: {e}")
        
        return news_list
    
    def _get_announcements(self, symbol: str, limit: int) -> List[NewsItem]:
        """获取公司公告"""
        news_list = []
        
        try:
            # 转换股票代码为东方财富格式
            # 600519 -> 600519
            # 000001 -> 000001
            market_map = {
                '6': 'sha',  # 沪市
                '0': 'sza',  # 深市主板
                '3': 'szb',  # 创业板
                '8': 'bj',   # 北交所
            }
            prefix = market_map.get(symbol[0], 'sha')
            
            url = 'https://np-anotice-stock.eastmoney.com/api/security/ann'
            params = {
                'sr': '-1',
                'page_size': limit,
                'page_index': 1,
                'ann_type': f'{prefix.upper()}%2CCYB%2CSZA',
                'stock_list': symbol,
                'client_source': 'web',
            }
            
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            items = data.get('data', {}).get('list', [])
            
            for item in items:
                try:
                    title = item.get('title', '')
                    content = item.get('summary', '')[:200]
                    url = f"https://np-anotice-stock.eastmoney.com/api/security/ann?aid={item.get('aid', '')}"
                    publish_time = item.get('publish_time', '')
                    
                    if not title:
                        continue
                    
                    published_at = datetime.fromtimestamp(publish_time / 1000) if publish_time else datetime.now()
                    
                    news_item = NewsItem(
                        title=title,
                        content=self._clean_html(content),
                        source=f'{self.name}_ann',
                        url=url,
                        published_at=published_at,
                    )
                    news_list.append(news_item)
                    
                except Exception as e:
                    self.logger.warning(f"解析公告失败: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"获取公告失败: {e}")
        
        return news_list
    
    def get_market_news(
        self, 
        market: str = 'china',
        limit: int = 20,
        start_date: Optional[datetime] = None
    ) -> List[NewsItem]:
        """获取市场新闻"""
        # 市场新闻使用搜索接口
        keywords = {
            'china': 'A股 今日 股市',
            'hk': '港股 今日',
            'us': '美股 今日',
        }
        
        keyword = keywords.get(market, keywords['china'])
        return self._search_news(keyword, limit)
```

---

## 4. 财新RSS新闻源

### 4.1 RSS源

```
财经: https://international.caixin.com/rss/latest.xml
经济: https://economy.caixin.com/rss/latest.xml
股市: https://finance.caixin.com/rss/finance.xml
公司: https://companies.caixin.com/rss/latest.xml
```

### 4.2 实现代码

```python
# agent_integration/dataflows/news/caixin.py

import feedparser
import re
from typing import List, Optional
from datetime import datetime, timedelta
from .base import BaseNewsSource, NewsItem, Sentiment

class CaixinNews(BaseNewsSource):
    """财新RSS新闻源"""
    
    name = 'caixin'
    base_url = 'https://international.caixin.com'
    
    RSS_FEEDS = {
        'finance': 'https://finance.caixin.com/rss/finance.xml',
        'economy': 'https://economy.caixin.com/rss/latest.xml',
        'companies': 'https://companies.caixin.com/rss/latest.xml',
        'international': 'https://international.caixin.com/rss/latest.xml',
    }
    
    def __init__(self):
        super().__init__()
        self.session = None  # feedparser不需要session
    
    def get_stock_news(
        self, 
        symbol: str, 
        limit: int = 20,
        start_date: Optional[datetime] = None
    ) -> List[NewsItem]:
        """获取财新新闻 (按关键词过滤)"""
        # 获取所有最新新闻
        all_news = self.get_market_news('china', limit * 2)
        
        # 简单关键词匹配
        # 注: 财新RSS不提供股票代码，需通过标题匹配
        filtered = []
        for news in all_news:
            # 简单检查标题是否包含股票相关信息
            keywords = ['茅台', '银行', '保险', '证券', '科技', '地产', '能源']
            if any(kw in news.title for kw in keywords):
                filtered.append(news)
        
        return filtered[:limit]
    
    def get_market_news(
        self, 
        market: str = 'china',
        limit: int = 20,
        start_date: Optional[datetime] = None
    ) -> List[NewsItem]:
        """获取财新市场新闻"""
        news_list = []
        
        # 选择合适的RSS源
        feed_url = self.RSS_FEEDS.get('finance', self.RSS_FEEDS['international'])
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:limit * 2]:  # 多取一些用于过滤
                try:
                    title = entry.get('title', '')
                    content = entry.get('summary', '')[:200]
                    url = entry.get('link', '')
                    published_parsed = entry.get('published_parsed')
                    
                    if not title or not url:
                        continue
                    
                    if published_parsed:
                        published_at = datetime(*published_parsed[:6])
                    else:
                        published_at = datetime.now()
                    
                    # 过滤日期
                    if start_date and published_at < start_date:
                        continue
                    
                    news_item = NewsItem(
                        title=self._clean_html(title),
                        content=self._clean_html(content),
                        source=self.name,
                        url=url,
                        published_at=published_at,
                    )
                    news_list.append(news_item)
                    
                except Exception as e:
                    self.logger.warning(f"解析RSS条目失败: {e}")
                    continue
                
        except Exception as e:
            self.logger.error(f"获取财新RSS失败: {e}")
        
        # 按时间排序
        news_list.sort(key=lambda x: x.published_at, reverse=True)
        return news_list[:limit]
```

---

## 5. 新浪财经新闻源

### 5.1 接口分析

**新闻列表接口**:
```
URL: https://feed.mix.sina.com.cn/api/roll/get
Method: GET
Params:
  - pageid=153&lid=2517&k=贵州茅台
  - page=1
  - num=20
  - r=0.5 (随机)
```

**财经频道**:
- 宏观: lid=2516
- 行业: lid=2517
- 公司: lid=1686

### 5.2 实现代码

```python
# agent_integration/dataflows/news/sina.py

import requests
import json
import random
from typing import List, Optional
from datetime import datetime
from .base import BaseNewsSource, NewsItem, Sentiment

class SinaNews(BaseNewsSource):
    """新浪财经新闻源"""
    
    name = 'sina'
    base_url = 'https://feed.mix.sina.com.cn'
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/',
        })
    
    def get_stock_news(
        self, 
        symbol: str, 
        limit: int = 20,
        start_date: Optional[datetime] = None
    ) -> List[NewsItem]:
        """获取新浪财经新闻"""
        news_list = []
        
        # 方法1: 搜索接口
        search_news = self._search_news(symbol, limit)
        news_list.extend(search_news)
        
        # 方法2: 财经频道
        channel_news = self._get_channel_news(limit)
        news_list.extend(channel_news)
        
        # 去重
        seen = set()
        unique_news = []
        for item in news_list:
            if item.url not in seen:
                seen.add(item.url)
                unique_news.append(item)
        
        unique_news.sort(key=lambda x: x.published_at, reverse=True)
        
        if start_date:
            unique_news = [n for n in unique_news if n.published_at >= start_date]
        
        return unique_news[:limit]
    
    def _search_news(self, keyword: str, limit: int) -> List[NewsItem]:
        """搜索新闻"""
        news_list = []
        
        try:
            params = {
                'pageid': 153,
                'lid': 2517,  # 行业
                'k': keyword,
                'page': 1,
                'num': limit,
                'r': random.random(),
            }
            
            response = self.session.get(
                f"{self.base_url}/api/roll/get", 
                params=params, 
                timeout=10
            )
            data = response.json()
            
            items = data.get('result', {}).get('data', [])
            
            for item in items:
                try:
                    title = item.get('title', '')
                    content = item.get('intro', '')[:200]
                    url = item.get('url', '')
                    datetime_str = item.get('datetime', '')
                    
                    if not title or not url:
                        continue
                    
                    published_at = self._parse_datetime(datetime_str)
                    if not published_at:
                        published_at = datetime.now()
                    
                    news_item = NewsItem(
                        title=self._clean_html(title),
                        content=self._clean_html(content),
                        source=self.name,
                        url=url,
                        published_at=published_at,
                    )
                    news_list.append(news_item)
                    
                except Exception as e:
                    self.logger.warning(f"解析新闻条目失败: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"搜索新闻失败: {e}")
        
        return news_list
    
    def _get_channel_news(self, limit: int) -> List[NewsItem]:
        """获取财经频道新闻"""
        news_list = []
        
        try:
            params = {
                'pageid': 153,
                'lid': 2516,  # 宏观
                'page': 1,
                'num': limit,
                'r': random.random(),
            }
            
            response = self.session.get(
                f"{self.base_url}/api/roll/get",
                params=params,
                timeout=10
            )
            data = response.json()
            
            items = data.get('result', {}).get('data', [])
            
            for item in items:
                try:
                    title = item.get('title', '')
                    content = item.get('intro', '')[:200]
                    url = item.get('url', '')
                    datetime_str = item.get('datetime', '')
                    
                    if not title or not url:
                        continue
                    
                    published_at = self._parse_datetime(datetime_str)
                    if not published_at:
                        published_at = datetime.now()
                    
                    news_item = NewsItem(
                        title=self._clean_html(title),
                        content=self._clean_html(content),
                        source=f'{self.name}_channel',
                        url=url,
                        published_at=published_at,
                    )
                    news_list.append(news_item)
                    
                except Exception as e:
                    self.logger.warning(f"解析新闻条目失败: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"获取频道新闻失败: {e}")
        
        return news_list
    
    def get_market_news(
        self, 
        market: str = 'china',
        limit: int = 20,
        start_date: Optional[datetime] = None
    ) -> List[NewsItem]:
        """获取市场新闻"""
        keywords = {
            'china': 'A股',
            'hk': '港股',
            'us': '美股',
        }
        
        keyword = keywords.get(market, keywords['china'])
        return self._search_news(keyword, limit)
```

---

## 6. Google News新闻源

### 6.1 实现方案

使用Google News搜索，通过RSS或非官方API实现。

```python
# agent_integration/dataflows/news/google_news.py

import requests
import feedparser
import random
from typing import List, Optional
from datetime import datetime
from .base import BaseNewsSource, NewsItem, Sentiment

class GoogleNews(BaseNewsSource):
    """Google News新闻源"""
    
    name = 'google_news'
    base_url = 'https://news.google.com'
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        })
    
    def get_stock_news(
        self, 
        symbol: str, 
        limit: int = 20,
        start_date: Optional[datetime] = None
    ) -> List[NewsItem]:
        """获取Google News新闻"""
        news_list = []
        
        # Google News搜索
        search_url = f"{self.base_url}/rss/search"
        params = {
            'q': f'{symbol} stock OR {symbol} 股票',
            'hl': 'zh-CN',  # 中文
            'gl': 'CN',     # 中国
            'ceid': 'CN:zh-Hans',
        }
        
        try:
            response = self.session.get(search_url, params=params, timeout=15)
            feed = feedparser.parse(response.content)
            
            for entry in feed.entries[:limit]:
                try:
                    title = entry.get('title', '')
                    content = entry.get('summary', '')[:200]
                    url = entry.get('link', '')
                    published_parsed = entry.get('published_parsed')
                    
                    if not title or not url:
                        continue
                    
                    if published_parsed:
                        published_at = datetime(*published_parsed[:6])
                    else:
                        published_at = datetime.now()
                    
                    if start_date and published_at < start_date:
                        continue
                    
                    news_item = NewsItem(
                        title=self._clean_html(title),
                        content=self._clean_html(content),
                        source=self.name,
                        url=url,
                        published_at=published_at,
                    )
                    news_list.append(news_item)
                    
                except Exception as e:
                    self.logger.warning(f"解析Google News条目失败: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"获取Google News失败: {e}")
        
        return news_list
    
    def get_market_news(
        self, 
        market: str = 'china',
        limit: int = 20,
        start_date: Optional[datetime] = None
    ) -> List[NewsItem]:
        """获取市场新闻"""
        keywords = {
            'china': 'China stock market OR A股',
            'hk': 'Hong Kong stock market OR 港股',
            'us': 'US stock market OR Wall Street',
        }
        
        search_url = f"{self.base_url}/rss/search"
        params = {
            'q': keywords.get(market, keywords['china']),
            'hl': 'zh-CN',
            'gl': 'CN',
            'ceid': 'CN:zh-Hans',
        }
        
        news_list = []
        
        try:
            response = self.session.get(search_url, params=params, timeout=15)
            feed = feedparser.parse(response.content)
            
            for entry in feed.entries[:limit]:
                try:
                    title = entry.get('title', '')
                    content = entry.get('summary', '')[:200]
                    url = entry.get('link', '')
                    published_parsed = entry.get('published_parsed')
                    
                    if not title or not url:
                        continue
                    
                    if published_parsed:
                        published_at = datetime(*published_parsed[:6])
                    else:
                        published_at = datetime.now()
                    
                    if start_date and published_at < start_date:
                        continue
                    
                    news_item = NewsItem(
                        title=self._clean_html(title),
                        content=self._clean_html(content),
                        source=self.name,
                        url=url,
                        published_at=published_at,
                    )
                    news_list.append(news_item)
                    
                except Exception as e:
                    self.logger.warning(f"解析条目失败: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"获取市场新闻失败: {e}")
        
        return news_list
```

---

## 7. 新闻聚合器

```python
# agent_integration/dataflows/news/aggregator.py

from typing import List, Optional, Dict
from datetime import datetime, timedelta
import logging

from .base import BaseNewsSource
from .eastmoney import EastMoneyNews
from .sina import SinaNews
from .caixin import CaixinNews
from .google_news import GoogleNews
from .schema import NewsItem, StockNewsResult
from .sentiment import SentimentAnalyzer

logger = logging.getLogger(__name__)

class NewsAggregator:
    """
    新闻聚合器 - 整合多源新闻
    """
    
    def __init__(self, use_llm_sentiment: bool = False):
        """
        初始化聚合器
        
        Args:
            use_llm_sentiment: 是否使用LLM进行情感分析
        """
        self.sources = {
            'eastmoney': EastMoneyNews(),
            'sina': SinaNews(),
            'caixin': CaixinNews(),
            'google': GoogleNews(),
        }
        
        self.default_sources = ['eastmoney', 'sina', 'caixin']
        self.sentiment_analyzer = SentimentAnalyzer(use_llm=use_llm_sentiment)
    
    def get_stock_news(
        self,
        symbol: str,
        sources: Optional[List[str]] = None,
        limit: int = 20,
        include_sentiment: bool = True,
        start_date: Optional[datetime] = None
    ) -> StockNewsResult:
        """
        获取股票新闻
        
        Args:
            symbol: 股票代码
            sources: 使用的新闻源 (默认 ['eastmoney', 'sina', 'caixin'])
            limit: 返回数量
            include_sentiment: 是否进行情感分析
            start_date: 开始日期
            
        Returns:
            StockNewsResult: 聚合后的新闻结果
        """
        if sources is None:
            sources = self.default_sources
        
        if start_date is None:
            start_date = datetime.now() - timedelta(days=7)
        
        all_news = []
        successful_sources = []
        
        for source_name in sources:
            if source_name not in self.sources:
                logger.warning(f"未知的新闻源: {source_name}")
                continue
            
            try:
                source = self.sources[source_name]
                news = source.get_stock_news(symbol, limit, start_date)
                
                if news:
                    all_news.extend(news)
                    successful_sources.append(source_name)
                    logger.info(f"{source_name} 返回 {len(news)} 条新闻")
                    
            except Exception as e:
                logger.error(f"{source_name} 获取新闻失败: {e}")
                continue
        
        # 去重 (按URL)
        seen = set()
        unique_news = []
        for item in all_news:
            if item.url not in seen:
                seen.add(item.url)
                unique_news.append(item)
        
        # 情感分析
        if include_sentiment:
            for news in unique_news:
                sentiment, score = self.sentiment_analyzer.analyze(news.content)
                news.sentiment = sentiment
                news.sentiment_score = score
        
        # 按时间排序
        unique_news.sort(key=lambda x: x.published_at, reverse=True)
        
        return StockNewsResult(
            symbol=symbol,
            news=unique_news[:limit],
            total_count=len(unique_news),
            fetched_at=datetime.now(),
            sources=successful_sources,
        )
    
    def get_market_news(
        self,
        market: str = 'china',
        sources: Optional[List[str]] = None,
        limit: int = 20,
        include_sentiment: bool = True,
        start_date: Optional[datetime] = None
    ) -> List[NewsItem]:
        """获取市场整体新闻"""
        if sources is None:
            sources = self.default_sources
        
        if start_date is None:
            start_date = datetime.now() - timedelta(days=7)
        
        all_news = []
        
        for source_name in sources:
            if source_name not in self.sources:
                continue
            
            try:
                source = self.sources[source_name]
                news = source.get_market_news(market, limit, start_date)
                all_news.extend(news)
            except Exception as e:
                logger.error(f"{source_name} 获取市场新闻失败: {e}")
                continue
        
        # 去重
        seen = set()
        unique_news = []
        for item in all_news:
            if item.url not in seen:
                seen.add(item.url)
                unique_news.append(item)
        
        # 情感分析
        if include_sentiment:
            for news in unique_news:
                sentiment, score = self.sentiment_analyzer.analyze(news.content)
                news.sentiment = sentiment
                news.sentiment_score = score
        
        unique_news.sort(key=lambda x: x.published_at, reverse=True)
        return unique_news[:limit]
```

---

## 8. 情感分析模块

### 8.1 中文情感词典

```python
# agent_integration/dataflows/news/sentiment.py

import re
from typing import Tuple, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class Sentiment(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

# 中文情感词典 (简化版)
POSITIVE_WORDS = [
    '上涨', '涨停', '突破', '增长', '超预期', '强劲', '利好', '盈利', '利润', '增长',
    '上调', '买入', '推荐', '增持', '扩张', '创新', '领先', '景气', '回暖', '复苏',
    '高增长', '业绩', '大幅增长', '开门红', '首板', '连板', '涨停板',
    '牛市', '多头', '做多', '看涨', '上升通道',
    '优质', '低估', '价值', '投资价值', '值得持有',
]

NEGATIVE_WORDS = [
    '下跌', '跌停', '破位', '亏损', '不及预期', '疲软', '利空', '风险', '减值', '下滑',
    '下调', '卖出', '减持', '收缩', '落后', '衰退', '风险', '暴雷', '违约', 'ST',
    '大幅下跌', '业绩下滑', '首板跌停', '炸板',
    '熊市', '空头', '做空', '看跌', '下降通道',
    '垃圾', '高估', '风险大', '规避', '远离',
]

@dataclass
class SentimentResult:
    sentiment: Sentiment
    score: float  # -1.0 ~ 1.0
    positive_words: List[str]
    negative_words: List[str]

class SentimentAnalyzer:
    """
    情感分析器
    
    支持两种模式:
    1. 词典模式 (默认): 使用情感词典匹配
    2. LLM模式: 调用LLM进行情感分析
    """
    
    def __init__(self, use_llm: bool = False, llm_adapter=None):
        """
        初始化情感分析器
        
        Args:
            use_llm: 是否使用LLM
            llm_adapter: LLM适配器
        """
        self.use_llm = use_llm
        self.llm_adapter = llm_adapter
    
    def analyze(self, text: str) -> Tuple[Sentiment, float]:
        """
        分析文本情感
        
        Args:
            text: 文本内容
            
        Returns:
            Tuple[Sentiment, float]: (情感类型, 分数)
        """
        if not text:
            return Sentiment.NEUTRAL, 0.0
        
        if self.use_llm and self.llm_adapter:
            return self._analyze_with_llm(text)
        else:
            return self._analyze_with_dict(text)
    
    def _analyze_with_dict(self, text: str) -> Tuple[Sentiment, float]:
        """使用词典分析"""
        # 统计正面词和负面词
        pos_count = 0
        neg_count = 0
        found_positive = []
        found_negative = []
        
        for word in POSITIVE_WORDS:
            if word in text:
                pos_count += 1
                found_positive.append(word)
        
        for word in NEGATIVE_WORDS:
            if word in text:
                neg_count += 1
                found_negative.append(word)
        
        # 计算分数
        total = pos_count + neg_count
        if total == 0:
            return Sentiment.NEUTRAL, 0.0
        
        # 分数范围: -1.0 ~ 1.0
        score = (pos_count - neg_count) / total
        
        # 判断情感
        if score > 0.2:
            sentiment = Sentiment.POSITIVE
        elif score < -0.2:
            sentiment = Sentiment.NEGATIVE
        else:
            sentiment = Sentiment.NEUTRAL
        
        return sentiment, score
    
    def _analyze_with_llm(self, text: str) -> Tuple[Sentiment, float]:
        """使用LLM分析 (需要LLM适配器)"""
        if not self.llm_adapter:
            return self._analyze_with_dict(text)
        
        prompt = f"""分析以下财经新闻的情感，判断是正面、负面还是中性。

新闻内容：
{text[:500]}

请只回答以下格式（不要有其他内容）：
正面,0.75
负面,-0.5
中性,0.0

分数范围：-1.0（极度负面）到 1.0（极度正面）
"""
        
        try:
            response = self.llm_adapter.generate(prompt)
            
            # 解析响应
            lines = response.strip().split('\n')
            first_line = lines[0]
            
            if '正面' in first_line:
                sentiment = Sentiment.POSITIVE
            elif '负面' in first_line:
                sentiment = Sentiment.NEGATIVE
            else:
                sentiment = Sentiment.NEUTRAL
            
            # 提取分数
            import re
            match = re.search(r'[-+]?\d*\.?\d+', first_line)
            if match:
                score = float(match.group())
            else:
                score = 0.0
            
            return sentiment, max(-1.0, min(1.0, score))
            
        except Exception as e:
            logger.error(f"LLM情感分析失败: {e}")
            return self._analyze_with_dict(text)
```

---

## 9. 目录结构

```
agent_integration/dataflows/
├── __init__.py
│
├── news/                      # 新闻模块
│   ├── __init__.py
│   ├── schema.py            # 数据结构
│   ├── base.py              # 基类
│   ├── eastmoney.py          # 东方财富
│   ├── sina.py              # 新浪财经
│   ├── caixin.py            # 财新RSS
│   ├── google_news.py        # Google News
│   ├── sentiment.py          # 情感分析
│   └── aggregator.py         # 聚合器
│
├── adapters/                  # 适配器
│   ├── __init__.py
│   ├── stock_data_adapter.py
│   ├── news_adapter.py
│   ├── cache_adapter.py
│   └── source_failover.py
│
├── interface.py               # 统一接口
└── data_source_manager.py    # 数据源管理
```

---

## 10. 使用示例

```python
from agent_integration.dataflows.news import NewsAggregator

# 初始化聚合器 (使用词典情感分析)
aggregator = NewsAggregator(use_llm_sentiment=False)

# 获取股票新闻
result = aggregator.get_stock_news(
    symbol='600519',  # 贵州茅台
    sources=['eastmoney', 'sina', 'caixin'],
    limit=20,
    include_sentiment=True
)

print(f"获取到 {result.total_count} 条新闻")
print(f"使用的数据源: {result.sources}")

for news in result.news:
    print(f"\n[{news.sentiment.value}] {news.title}")
    print(f"来源: {news.source} | 时间: {news.published_at}")
    print(f"情感分数: {news.sentiment_score:.2f}")
    print(f"摘要: {news.content[:100]}...")
```

---

## 11. 后续优化

### 11.1 短期优化

- [ ] 添加更多中文新闻源 (腾讯财经, 凤凰财经, 网易财经)
- [ ] 优化情感词典 (扩展正面/负面词库)
- [ ] 添加新闻去重算法 (SimHash)

### 11.2 中期优化

- [ ] 支持LLM情感分析 (使用DeepSeek/智谱)
- [ ] 添加股票代码自动识别
- [ ] 实现新闻热度计算

### 11.3 长期优化

- [ ] 支持港股/美股新闻
- [ ] 实现新闻事件抽取
- [ ] 构建新闻知识图谱

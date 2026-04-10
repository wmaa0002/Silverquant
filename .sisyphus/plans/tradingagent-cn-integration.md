# TradingAgents-CN 多智能体系统集成方案

> **生成时间**: 2026-03-29
> **源项目**: TradingAgents-CN (https://github.com/hsliuping/TradingAgents-CN)
> **目标项目**: 股票策略 (A股量化交易回测系统)

---

## 1. 背景与目标

### 1.1 源项目分析 (TradingAgents-CN)

**核心定位**: 基于LangChain/LangGraph的多智能体股票分析框架（教育研究用）

**开源部分 (Apache 2.0)**:
- `tradingagents/` - 核心多智能体框架
- `web/` - Streamlit旧版界面
- `cli/` - 命令行工具

**专有部分 (需商业授权)**:
- `app/` - FastAPI后端
- `frontend/` - Vue 3前端

### 1.2 目标项目分析 (股票策略)

**现有架构**:
```
股票策略/
├── config/          # 配置管理
├── database/        # DuckDB单例管理
├── data/            # 数据层 (akshare/baostock)
├── strategies/      # 策略模块 (backtrader)
├── signals/         # 信号计算
├── backtest/        # 回测引擎
├── tools/           # 可视化/分析工具
├── dashboard/       # Flask Web界面 (端口5001)
└── agent_integration/ # AI集成占位目录
```

### 1.3 集成目标

```
┌─────────────────────────────────────────────────────────────────────┐
│                      集成后的目标架构                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Flask Dashboard (已有)                       │  │
│  │                  端口: 5001, 端口: 5002                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              TradingAgents Multi-Agent Layer                 │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐ │  │
│  │  │ Market  │ │News     │ │Social   │ │Fundamen-│ │China  │ │  │
│  │  │ Analyst │ │Analyst  │ │Analyst  │ │tals     │ │Market │ │  │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └───┬───┘ │  │
│  │       └───────────┴───────────┴───────────┘           │      │  │
│  │                         ▼                             ▼      │  │
│  │       ┌─────────────────────────────────────────────┐       │  │
│  │       │     Bull Researcher  │  Bear Researcher    │       │  │
│  │       └──────────────────────┬──────────────────────┘       │  │
│  │                              ▼                              │  │
│  │                    Research Manager                         │  │
│  │                              ▼                              │  │
│  │       ┌──────────┬──────────┬──────────┐                   │  │
│  │       │Conserv-  │ Neutral  │Aggressive│                   │  │
│  │       │ative     │ Debater  │ Debater  │                   │  │
│  │       └─────┬────┴────┬─────┴────┬─────┘                   │  │
│  │             └─────────┴──────────┘                          │  │
│  │                         ▼                                   │  │
│  │                   Risk Manager                               │  │
│  │                         ▼                                   │  │
│  │                      Trader                                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   LLM Adapter Layer                         │  │
│  │   DeepSeek │ 阿里百炼 │ 百度千帆 │ 智谱AI │ OpenAI │ Gemini │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   DataFlows Layer                            │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │  │
│  │  │akshare  │ │tushare  │ │baostock │ │ yfinance│            │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘            │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                        │  │
│  │  │News API │ │ FinnHub │ │ Google  │                        │  │
│  │  │         │ │         │ │ News    │                        │  │
│  │  └─────────┘ └─────────┘ └─────────┘                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              已有数据层 (DuckDB + akshare/baostock)          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 集成范围

### 2.1 IN (纳入集成)

| 模块 | 源文件 | 目标位置 | 说明 |
|------|--------|----------|------|
| **多智能体框架** | `tradingagents/graph/` | `agent_integration/graph/` | LangGraph编排引擎 |
| **分析师Agent** | `tradingagents/agents/analysts/` | `agent_integration/agents/analysts/` | 5个分析师 |
| **研究员Agent** | `tradingagents/agents/researchers/` | `agent_integration/agents/researchers/` | 2个研究员 |
| **管理器Agent** | `tradingagents/agents/managers/` | `agent_integration/agents/managers/` | 2个管理器 |
| **风险辩论Agent** | `tradingagents/agents/risk_mgmt/` | `agent_integration/agents/risk_mgmt/` | 3个风险辩论 |
| **交易员Agent** | `tradingagents/agents/trader/` | `agent_integration/agents/trader/` | 交易执行 |
| **LLM适配器** | `tradingagents/llm_adapters/` | `agent_integration/llm_adapters/` | 多提供商支持 |
| **数据流** | `tradingagents/dataflows/` | `agent_integration/dataflows/` | 数据源+缓存 |
| **向量记忆** | `tradingagents/agents/*_memory.py` | `agent_integration/memory/` | ChromaDB记忆 |

### 2.2 OUT (明确排除)

| 模块 | 原因 |
|------|------|
| `app/` (FastAPI后端) | 专有软件，与Flask不兼容 |
| `frontend/` (Vue前端) | 专有软件，已有Flask Dashboard |
| `web/` (Streamlit) | 重复功能 |
| `scripts/` (353个脚本) | 重复的调度脚本 |

### 2.3 适配层 (需要开发)

| 适配层 | 职责 |
|--------|------|
| **数据适配器** | 将TradingAgents的数据流适配到DuckDB |
| **配置适配器** | 对接`股票策略`的Settings到TradingAgents |
| **结果适配器** | 将分析结果存入现有数据库 |

---

## 3. 数据流架构详细设计

### 3.1 现有系统数据流分析

**股票策略项目现有数据流**:
```
StockFetcher (data/fetchers/stock_fetcher.py)
    │
    ├── akshare ──→ get_stock_list(), get_daily_price()
    ├── baostock ──→ query_history_k_data_plus()
    └── tushare ──→ pro_bar(), daily()
            │
            ▼
    DatabaseManager (DuckDB)
            │
            ▼
    backtrader回测引擎
```

**TradingAgents-CN数据流**:
```
DataFlows Layer
    │
    ├── interface.py (统一入口)
    │       │
    │       ├── get_china_stock_data_unified() ──→ providers/china/
    │       ├── get_stock_news() ──→ news/
    │       └── get_fundamentals() ──→ providers/
    │
    ├── data_source_manager.py (多数据源管理+降级)
    │       │
    │       ├── MongoDB Cache
    │       ├── Tushare ──→ AKShare ──→ Baostock (降级链)
    │       └── 缓存管理
    │
    └── optimized_china_data.py (缓存+分析)
            │
            ▼
    LangGraph Agents (13个智能体)
```

### 3.2 数据流集成架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    数据流集成架构                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Multi-Agent Layer                              │   │
│  │  Market Analyst │ News Analyst │ Fundamentals Analyst │ ...      │   │
│  └─────────────────────────────────┬───────────────────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Unified Data Interface (interface.py)               │   │
│  │                                                                  │   │
│  │  get_china_stock_data_unified()    ←─── 股票策略的StockFetcher    │   │
│  │  get_china_stock_news()            ←─── TradingAgents新闻源       │   │
│  │  get_china_fundamentals_cached()   ←─── 股票策略DuckDB           │   │
│  │  get_social_sentiment()            ←─── TradingAgents情感分析     │   │
│  └─────────────────────────────────┬───────────────────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Data Source Manager (适配层)                        │   │
│  │                                                                  │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │                  复用层 (保留TradingAgents优势)           │    │   │
│  │  │  • 统一缓存管理 (Redis/MongoDB/File)                     │    │   │
│  │  │  • 多源降级机制 (Tushare → AKShare → Baostock)           │    │   │
│  │  │  • 新闻聚合 (Google News, FinnHub, 财新, 东方财富)        │    │   │
│  │  │  • 社交情绪 (Reddit, 微博, 股吧)                         │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  │                              │                                   │   │
│  │                              ▼                                   │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │                  适配层 (新开发)                          │    │   │
│  │  │                                                          │    │   │
│  │  │  StockDataAdapter ──────→ 复用股票策略的StockFetcher      │    │   │
│  │  │  DuckDBAdapter  ──────→ 复用DatabaseManager            │    │   │
│  │  │  ConfigAdapter   ──────→ 复用Settings配置              │    │   │
│  │  │                                                          │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    现有数据层 (股票策略)                          │   │
│  │                                                                  │   │
│  │  StockFetcher ──→ akshare/baostock/tushare                       │   │
│  │        │                                                          │   │
│  │        ▼                                                          │   │
│  │  DatabaseManager ──→ DuckDB (Astock3.duckdb)                     │   │
│  │        │                                                          │   │
│  │        ▼                                                          │   │
│  │  已有表: stock_info, daily_price, factor_data, backtest_*         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 核心接口设计

```python
# agent_integration/dataflows/adapters/stock_data_adapter.py

class StockDataAdapter:
    """
    股票数据适配器 - 桥接TradingAgents和股票策略的数据层
    
    职责:
    1. 将TradingAgents的数据请求转换为股票策略格式
    2. 优先使用股票策略的DuckDB数据
    3. 数据不足时调用akshare/baostock补充
    """
    
    def __init__(self, data_source: str = None):
        self._fetcher = StockFetcher(source=data_source)
        self._db = DatabaseManager.get_instance()
    
    def get_market_data(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str,
        fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        获取市场数据 (K线)
        
        优先级:
        1. DuckDB缓存数据
        2. akshare实时数据
        
        Returns:
            Dict: {
                'date': '2024-05-10',
                'open': 1800.0,
                'high': 1850.0,
                'low': 1790.0,
                'close': 1845.0,
                'volume': 1500000,
                'turnover': 2.5,
                ...
            }
        """
        
    def get_fundamentals(
        self, 
        symbol: str, 
        period: str = 'annual'
    ) -> Dict[str, Any]:
        """
        获取基本面数据
        
        优先从DuckDB获取，若无则从akshare/baostock获取
        """
        
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票基本信息"""
        
    def get_industry(self, symbol: str) -> str:
        """获取所属行业"""
```

```python
# agent_integration/dataflows/adapters/news_adapter.py

class NewsAdapter:
    """
    新闻数据适配器 - 整合多源新闻
    
    支持的新闻源:
    1. 东方财富 (eastmoney) - 免费，中文，实时
    2. 财新 (caixin) - RSS订阅
    3. Google News - 全球新闻
    4. FinnHub - 需要API Key，英文
    5. Alpha Vantage - 需要API Key，英文
    """
    
    def __init__(self):
        self._sources = {
            'eastmoney': EastMoneyNews(),
            'caixin': CaixinRSS(),
            'google_news': GoogleNewsScraper(),
            # 'finnhub': FinnHubNews(api_key=...),  # 需要Key
            # 'alpha_vantage': AlphaVantageNews(api_key=...),  # 需要Key
        }
        self._default_sources = ['eastmoney', 'caixin']
    
    def get_stock_news(
        self, 
        symbol: str, 
        market: str = 'china',
        limit: int = 20
    ) -> List[Dict]:
        """
        获取股票相关新闻
        
        Args:
            symbol: 股票代码 (e.g., '600519', '000001')
            market: 市场 ('china', 'hk', 'us')
            limit: 返回数量
            
        Returns:
            List[Dict]: [{
                'title': '茅台发布年报',
                'content': '...',
                'source': 'eastmoney',
                'published_at': '2024-05-10 10:30:00',
                'url': '...',
                'sentiment': 'positive',  # 情绪分析
                'sentiment_score': 0.75,
            }]
        """
        
    def get_market_news(
        self, 
        market: str = 'china',
        limit: int = 20
    ) -> List[Dict]:
        """获取市场整体新闻"""
```

```python
# agent_integration/dataflows/adapters/cache_adapter.py

class CacheAdapter:
    """
    缓存适配器 - 三级缓存
    
    Level 1: Redis (热点数据, TTL=5min)
    Level 2: DuckDB (历史数据, TTL=1h)  
    Level 3: File (原始API响应, TTL=24h)
    """
    
    def __init__(self):
        self._redis_client = None  # 可选
        self._db = DatabaseManager.get_instance()
        self._file_cache_dir = './dataflows/cache/'
    
    def get(
        self, 
        key: str, 
        level: int = 1
    ) -> Optional[Any]:
        """获取缓存"""
        
    def set(
        self, 
        key: str, 
        value: Any, 
        level: int = 1,
        ttl: int = None
    ) -> None:
        """设置缓存"""
        
    def invalidate(self, key: str) -> None:
        """失效缓存"""
```

### 3.4 新闻数据源详细设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         新闻数据源架构                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  NewsAdapter.get_stock_news("600519")                                   │
│           │                                                              │
│           ├──┌─────────────────────────────────────────────────────┐    │
│           │  │              Source: eastmoney (东方财富)            │    │
│           │  │  • 免费, 中文, 实时                                    │    │
│           │  │  • URL: https://news.eastmoney.com/                   │    │
│           │  │  • API: eastmoney_news_search()                       │    │
│           │  └─────────────────────────────────────────────────────┘    │
│           │                                                              │
│           ├──┌─────────────────────────────────────────────────────┐    │
│           │  │              Source: caixin (财新)                   │    │
│           │  │  • RSS订阅, 高质量                                    │    │
│           │  │  • URL: http://international.caixin.com/rss/         │    │
│           │  └─────────────────────────────────────────────────────┘    │
│           │                                                              │
│           ├──┌─────────────────────────────────────────────────────┐    │
│           │  │              Source: google_news (Google)             │    │
│           │  │  • 全球覆盖, 英文为主                                 │    │
│           │  │  • Web Scraping                                     │    │
│           │  └─────────────────────────────────────────────────────┘    │
│           │                                                              │
│           └──┌─────────────────────────────────────────────────────┐    │
│              │              Source: sina (新浪)                      │    │
│              │  • 免费, 中文, 实时                                    │    │
│              │  • URL: https://finance.sina.com.cn/                  │    │
│              └─────────────────────────────────────────────────────┘    │
│                                                                         │
│           │                                                              │
│           ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Sentiment Analysis                             │   │
│  │                                                                  │   │
│  │  1. 中文情感分析: jieba + 词典匹配                            │   │
│  │     • 正面词: 上涨, 突破, 增长, 超预期...                      │   │
│  │     • 负面词: 下跌, 风险, 亏损, 预警...                        │   │
│  │                                                                  │   │
│  │  2. LLM情感分析 (可选):                                        │   │
│  │     • 调用LLM分析新闻情绪                                       │   │
│  │     • 返回 sentiment + score                                   │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│           │                                                              │
│           ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Cache Layer                                    │   │
│  │                                                                  │   │
│  │  key = f"news:{symbol}:{date}"                                  │   │
│  │  TTL = 5min (盘中), 1h (盘后)                                   │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.5 数据源降级链

```python
# agent_integration/dataflows/adapters/source_failover.py

class SourceFailover:
    """
    数据源降级管理
    
    A股市场降级链:
    ┌────────────────────────────────────────────────────────────┐
    │ Level 1: Tushare (需要Token, 数据最全)                    │
    │           └─→ 若失败                                         │
    │ Level 2: AKShare (免费, 数据较好)                          │
    │           └─→ 若失败                                         │
    │ Level 3: Baostock (免费, 数据基本可用)                      │
    │           └─→ 若失败                                         │
    │ Level 4: 报错 (无可用数据源)                               │
    └────────────────────────────────────────────────────────────┘
    
    新闻降级链:
    ┌────────────────────────────────────────────────────────────┐
    │ Level 1: eastmoney (东方财富, 免费实时)                    │
    │           └─→ 若失败                                         │
    │ Level 2: sina (新浪财经, 免费)                              │
    │           └─→ 若失败                                         │
    │ Level 3: google_news (Google, 英文)                        │
    │           └─→ 若失败                                         │
    │ Level 4: 返回空列表                                        │
    └────────────────────────────────────────────────────────────┘
    """
    
    def get_market_data_with_failover(symbol, start, end):
        """带降级的市场数据获取"""
        for source in ['tushare', 'akshare', 'baostock']:
            try:
                data = fetcher.get_daily_price(symbol, start, end)
                if data is not None and not data.empty:
                    return data
            except Exception as e:
                logger.warning(f"{source}获取{symbol}失败: {e}, 尝试下一个源")
                continue
        raise DataSourceError(f"所有数据源均失败: {symbol}")
```

---

### 4.1 目录结构设计

```
agent_integration/
├── __init__.py
│
├── graph/                      # LangGraph编排
│   ├── __init__.py
│   ├── trading_graph.py        # 核心入口 (改编自tradingagents)
│   ├── state.py                # AgentState定义
│   ├── propagation.py          # 状态传播
│   └── conditional_logic.py    # 条件分支
│
├── agents/                     # 智能体
│   ├── __init__.py
│   ├── analysts/              # 5个分析师
│   │   ├── __init__.py
│   │   ├── market_analyst.py
│   │   ├── fundamentals_analyst.py
│   │   ├── news_analyst.py
│   │   ├── social_media_analyst.py
│   │   └── china_market_analyst.py
│   ├── researchers/            # 2个研究员
│   │   ├── __init__.py
│   │   ├── bull_researcher.py
│   │   └── bear_researcher.py
│   ├── managers/              # 2个管理器
│   │   ├── __init__.py
│   │   ├── research_manager.py
│   │   └── risk_manager.py
│   ├── risk_mgmt/            # 3个风险辩论
│   │   ├── __init__.py
│   │   ├── conservative_debator.py
│   │   ├── neutral_debator.py
│   │   └── aggressive_debator.py
│   └── trader/               # 交易员
│       ├── __init__.py
│       └── trader.py
│
├── llm_adapters/              # LLM适配层
│   ├── __init__.py
│   ├── base.py                # OpenAICompatibleBase基类
│   ├── deepseek.py
│   ├── dashscope.py           # 阿里百炼
│   ├── qianfan.py             # 百度千帆
│   ├── zhipu.py               # 智谱AI
│   ├── google.py              # Google Gemini
│   └── factory.py             # 工厂函数
│
├── dataflows/                 # ★数据流 (重点)
│   ├── __init__.py
│   │
│   ├── interface.py            # 统一接口入口 (改编自tradingagents)
│   ├── data_source_manager.py # 多数据源管理 (改编自tradingagents)
│   │
│   ├── adapters/              # ★适配器 (新开发)
│   │   ├── __init__.py
│   │   ├── stock_data_adapter.py   # 股票数据适配器
│   │   ├── news_adapter.py         # 新闻适配器
│   │   ├── cache_adapter.py        # 缓存适配器
│   │   └── source_failover.py     # 降级管理
│   │
│   ├── providers/             # 数据源 (复用/改编)
│   │   ├── __init__.py
│   │   ├── base_provider.py
│   │   ├── china/             # A股 (akshare/baostock/tushare)
│   │   ├── hk/               # 港股
│   │   └── us/               # 美股
│   │
│   ├── news/                  # ★新闻源 (新开发)
│   │   ├── __init__.py
│   │   ├── base.py           # 新闻基类
│   │   ├── eastmoney.py      # 东方财富
│   │   ├── sina.py          # 新浪财经
│   │   ├── caixin.py        # 财新RSS
│   │   ├── google_news.py   # Google新闻
│   │   ├── sentiment.py      # 情感分析
│   │   └── aggregator.py     # 新闻聚合器
│   │
│   └── cache/                 # 缓存层
│       ├── __init__.py
│       ├── redis_cache.py
│       ├── duckdb_cache.py   # ★复用DatabaseManager
│       └── file_cache.py
│
├── memory/                     # 向量记忆
│   ├── __init__.py
│   ├── chromadb_memory.py
│   └── memory_factory.py
│
└── api/                        # 对外API
    ├── __init__.py
    ├── analyzer.py            # 分析服务
    └── batch_analyzer.py       # 批量分析
```
agent_integration/
├── __init__.py
├── graph/                      # LangGraph编排
│   ├── __init__.py
│   ├── trading_graph.py         # 核心入口 (改编自tradingagents)
│   ├── state.py                 # AgentState定义
│   ├── propagation.py           # 状态传播
│   └── conditional_logic.py      # 条件分支
│
├── agents/                      # 智能体
│   ├── __init__.py
│   ├── analysts/               # 5个分析师
│   │   ├── __init__.py
│   │   ├── market_analyst.py
│   │   ├── fundamentals_analyst.py
│   │   ├── news_analyst.py
│   │   ├── social_media_analyst.py
│   │   └── china_market_analyst.py
│   ├── researchers/             # 2个研究员
│   │   ├── __init__.py
│   │   ├── bull_researcher.py
│   │   └── bear_researcher.py
│   ├── managers/               # 2个管理器
│   │   ├── __init__.py
│   │   ├── research_manager.py
│   │   └── risk_manager.py
│   ├── risk_mgmt/             # 3个风险辩论
│   │   ├── __init__.py
│   │   ├── conservative_debator.py
│   │   ├── neutral_debator.py
│   │   └── aggressive_debator.py
│   └── trader/                 # 交易员
│       ├── __init__.py
│       └── trader.py
│
├── llm_adapters/               # LLM适配层
│   ├── __init__.py
│   ├── base.py                 # OpenAICompatibleBase基类
│   ├── deepseek.py
│   ├── dashscope.py            # 阿里百炼
│   ├── qianfan.py              # 百度千帆
│   ├── zhipu.py                # 智谱AI
│   ├── google.py               # Google Gemini
│   └── factory.py             # 工厂函数
│
├── dataflows/                   # 数据流
│   ├── __init__.py
│   ├── providers/              # 数据源
│   │   ├── __init__.py
│   │   ├── china/             # A股数据 (复用现有)
│   │   ├── hk/                # 港股数据
│   │   └── us/                # 美股数据
│   ├── news/                   # 新闻源
│   │   ├── __init__.py
│   │   ├── google_news.py
│   │   ├── finnhub_news.py
│   │   ├── alpha_vantage_news.py
│   │   └── chinese_news.py
│   └── cache/                  # 缓存层
│       ├── __init__.py
│       ├── redis_cache.py
│       ├── mongo_cache.py
│       └── file_cache.py
│
├── memory/                      # 向量记忆
│   ├── __init__.py
│   ├── chromadb_memory.py
│   └── memory_factory.py
│
├── adapters/                    # 适配器 (新开发)
│   ├── __init__.py
│   ├── data_adapter.py         # 数据层适配
│   ├── config_adapter.py       # 配置适配
│   └── result_adapter.py       # 结果适配
│
└── api/                         # 对外API
    ├── __init__.py
    ├── analyzer.py             # 分析服务
    └── batch_analyzer.py        # 批量分析
```

### 3.2 核心组件集成

#### 3.2.1 TradingAgentsGraph (核心入口)

```python
# agent_integration/graph/trading_graph.py

class TradingAgentsGraph:
    """
    多智能体分析图入口
    
    使用方式:
        from agent_integration import TradingAgentsGraph
        
        ta = TradingAgentsGraph(
            selected_analysts=["market", "news", "fundamentals"],
            provider="deepseek",      # 使用现有的LLM配置
            model="deepseek-chat"
        )
        result = ta.propagate("600519", "2024-05-10")
    """
    
    def __init__(
        self,
        selected_analysts: List[str] = ["market", "news", "fundamentals"],
        provider: str = "deepseek",
        model: str = "deepseek-chat",
        debug: bool = False,
        config: Dict[str, Any] = None
    ):
        # 1. 使用config_adapter加载股票策略的配置
        # 2. 初始化LLM (通过llm_adapters)
        # 3. 初始化DataFlows (通过dataflows + 已有akshare/baostock)
        # 4. 构建LangGraph
```

#### 3.2.2 LLM适配器工厂

```python
# agent_integration/llm_adapters/factory.py

def create_llm_by_provider(
    provider: str,
    model: str,
    api_key: str = None,
    base_url: str = None,
    temperature: float = 0.1,
    max_tokens: int = None
) -> ChatOpenAI:
    """
    根据提供商名称创建LLM实例
    
    支持的提供商:
    - deepseek: DeepSeek Chat
    - dashscope: 阿里百炼 (qwen-turbo, qwen-plus)
    - qianfan: 百度千帆 (ernie-3.5-8k)
    - zhipu: 智谱AI (glm-4)
    - google: Google Gemini
    - openai: OpenAI GPT-4
    - anthropic: Anthropic Claude
    """
```

#### 3.2.3 数据流适配

```python
# agent_integration/adapters/data_adapter.py

class StockDataAdapter:
    """
    将TradingAgents数据请求适配到股票策略的DuckDB/akshare/baostock
    """
    
    def get_stock_market_data(self, symbol: str, trade_date: str) -> Dict:
        """获取市场数据 -> 复用StockFetcher"""
        
    def get_stock_fundamentals(self, symbol: str) -> Dict:
        """获取财务数据 -> 查询DuckDB或akshare"""
        
    def get_stock_news(self, symbol: str, limit: int = 20) -> List[Dict]:
        """获取新闻 -> TradingAgents的新闻源"""
        
    def get_social_sentiment(self, symbol: str) -> Dict:
        """获取社交情绪 -> TradingAgents社交分析"""
```

### 3.3 配置对接

```python
# agent_integration/adapters/config_adapter.py

from config.settings import Settings

class ConfigAdapter:
    """
    将股票策略的Settings配置转换为TradingAgents格式
    """
    
    # LLM配置
    LLM_PROVIDER = Settings.LLM_PROVIDER  # 'deepseek' / 'dashscope' / etc
    LLM_MODEL = Settings.LLM_MODEL        # 模型名称
    LLM_API_KEY = Settings.LLM_API_KEY     # API密钥
    
    # 数据源配置 (TradingAgents支持的数据源)
    MARKET_DATA_SOURCE = Settings.DATA_SOURCE  # 'akshare' / 'baostock'
    
    # 缓存配置
    USE_REDIS = Settings.USE_REDIS_CACHE
    USE_MONGO = Settings.USE_MONGO_CACHE
```

### 3.4 新闻数据源集成

```python
# agent_integration/dataflows/news/ 集成方案

class NewsAggregator:
    """
    新闻数据聚合器 - 整合多源新闻
    """
    
    SOURCES = {
        # 英文新闻
        'finnhub': FinnHubNewsProvider(api_key=...),     # 需要API Key
        'alpha_vantage': AlphaVantageNews(api_key=...),  # 需要API Key
        'google_news': GoogleNewsScraper(),              # 免费
        
        # 中文新闻
        'eastmoney': EastMoneyNews(),                    # 免费
        'sina': SinaFinanceNews(),                       # 免费
        'caixin': CaixinRSSNews(),                       # 免费
    }
    
    def get_news(self, symbol: str, market: str = 'china') -> List[Dict]:
        """
        获取股票相关新闻
        
        Args:
            symbol: 股票代码 (e.g., '600519', '000001')
            market: 市场 ('china', 'hk', 'us')
        """
```

---

## 4. 使用方式

### 4.1 基础调用

```python
from agent_integration import TradingAgentsGraph

# 初始化 (使用配置适配器自动加载Settings)
ta = TradingAgentsGraph(
    selected_analysts=["market", "news", "fundamentals", "china_market"],
    debug=True
)

# 执行分析
decision = ta.propagate(
    company_of_interest="600519",  # 贵州茅台
    trade_date="2024-05-10"
)

print(decision)
# {
#     'decision': 'BUY',
#     'confidence': 0.85,
#     'reasoning': '...',
#     'risk_level': 'MODERATE',
#     'analyst_reports': {...},
#     'debate_summary': '...'
# }
```

### 4.2 批量分析

```python
from agent_integration import BatchAnalyzer

analyzer = BatchAnalyzer(
    providers=["deepseek", "dashscope"],  # 主备LLM
    max_workers=3
)

results = analyzer.analyze_stocks(
    stock_list=["600519", "000001", "300486"],
    analysts=["market", "news", "fundamentals"],
    start_date="2024-01-01",
    end_date="2024-12-31"
)

# 存入数据库
analyzer.save_to_database(results)
```

### 4.3 集成到回测流程

```python
from agent_integration import TradingAgentsGraph
from backtest.engine import BacktestEngine

# 在回测中集成AI信号
class AIEnhancedStrategy(BaseStrategy):
    def __init__(self):
        self.agent = TradingAgentsGraph(
            selected_analysts=["market", "news"]
        )
    
    def next(self):
        # 获取AI决策
        decision = self.agent.propagate(
            company_of_interest=self.code,
            trade_date=self.datetime.date()
        )
        
        if decision['decision'] == 'BUY':
            self.buy()
        elif decision['decision'] == 'SELL':
            self.sell()
```

---

## 5. 实施计划 (一周紧凑版)

**目标**: 一周内完成最小可用版本(MVP)

### 5.1 Day 1: 项目搭建 + LLM适配器

**目标**: 建立项目结构 + 基础LLM适配

| 任务 | 工作内容 | 文件 | 并行 |
|------|----------|------|------|
| **T1: 目录结构** | 创建agent_integration/目录 | - | - |
| **T2: LLM基类** | OpenAICompatibleBase + TokenTracker | `llm_adapters/base.py` | T1 |
| **T3: 工厂函数** | create_llm_by_provider | `llm_adapters/factory.py` | T2 |
| **T4: DeepSeek适配器** | DeepSeek Chat | `llm_adapters/deepseek.py` | T3 |
| **T5: MiniMax适配器** | MiniMax Chat (用户提供) | `llm_adapters/minimax.py` | T3 |
| **T6: 测试LLM调用** | 验证LLM连接 | - | T4,T5 |

**并行度**: T4,T5 基于T3

### 5.2 Day 2: 数据流核心

**目标**: 实现新闻数据获取 + 股票数据适配

| 任务 | 工作内容 | 文件 | 并行 | 依赖 |
|------|----------|------|------|------|
| **T7: 新闻基类** | BaseNewsSource | `dataflows/news/base.py` | - | T1 |
| **T8: 东方财富新闻** | EastMoneyNews | `dataflows/news/eastmoney.py` | T7后 | T7 |
| **T9: 新闻聚合器** | NewsAggregator | `dataflows/news/aggregator.py` | T8后 | T8 |
| **T10: 情感分析** | SentimentAnalyzer | `dataflows/news/sentiment.py` | T9后 | T9 |
| **T11: 股票数据适配器** | StockDataAdapter | `dataflows/adapters/stock_adapter.py` | - | T1 |

**并行度**: T8可与T11并行

### 5.3 Day 3: 分析师智能体

**目标**: 实现核心分析师 (技术分析 + 新闻分析)

| 任务 | 工作内容 | 文件 | 并行 | 依赖 |
|------|----------|------|------|------|
| **T12: Agent基类** | BaseAgent | `agents/base.py` | - | T1 |
| **T13: MarketAnalyst** | 技术分析师 | `agents/analysts/market_analyst.py` | T12后 | T12 |
| **T14: NewsAnalyst** | 新闻分析师 | `agents/analysts/news_analyst.py` | T12后 | T12,T10 |
| **T15: FundamentalsAnalyst** | 基本面分析师 | `agents/analysts/fundamentals_analyst.py` | T12后 | T12 |
| **T16: 分析师测试** | 验证分析师运行 | - | T13,T14,T15 | T6 |

**并行度**: T13,T14,T15可并行 (都基于T12)

### 5.4 Day 4: 研究员 + Graph

**目标**: 实现研究员 + 基本Graph编排

| 任务 | 工作内容 | 文件 | 并行 | 依赖 |
|------|----------|------|------|------|
| **T17: BullResearcher** | 看涨研究员 | `agents/researchers/bull_researcher.py` | - | T13,T14,T15 |
| **T18: BearResearcher** | 看跌研究员 | `agents/researchers/bear_researcher.py` | T17 | T13,T14,T15 |
| **T19: AgentState** | 状态定义 | `graph/state.py` | - | T12 |
| **T20: TradingAgentsGraph** | Graph入口 | `graph/trading_graph.py` | T19后 | T17,T18,T19 |

**并行度**: T17,T18可并行

### 5.5 Day 5: 管理器 + 简化决策

**目标**: 实现ResearchManager + 简化决策流程

| 任务 | 工作内容 | 文件 | 并行 | 依赖 |
|------|----------|------|------|------|
| **T21: ResearchManager** | 研究管理器 | `agents/managers/research_manager.py` | - | T17,T18 |
| **T22: RiskManager** | 风险管理器 | `agents/managers/risk_manager.py` | T21后 | T21 |
| **T23: Trader** | 交易员 | `agents/trader/trader.py` | T22后 | T22 |
| **T24: 简化辩论** | 合并3个debator为1个 | `agents/risk_mgmt/simple_debator.py` | T22后 | T22 |
| **T25: 端到端测试** | 完整流程测试 | - | T23,T24 | T20 |

### 5.6 Day 6: 集成 + 适配

**目标**: 与现有系统集成

| 任务 | 工作内容 | 文件 | 依赖 |
|------|----------|------|------|
| **T26: 配置适配器** | 对接Settings | `adapters/config_adapter.py` | T1 |
| **T27: 结果存储** | 存入DuckDB | `adapters/result_adapter.py` | T11 |
| **T28: Flask路由** | API封装 | `dashboard/agent_api.py` | T25 |
| **T29: 集成测试** | 与回测系统集成测试 | - | T26,T27,T28 |

### 5.7 Day 7: 优化 + 文档

**目标**: 优化 + 编写使用文档

| 任务 | 工作内容 | 依赖 |
|------|----------|------|
| T30: Token追踪优化 | 添加成本统计 | T6 |
| T31: 缓存优化 | 添加Redis缓存 (可选) | T11 |
| T32: 异常处理 | 完善错误处理和重试 | T25 |
| T33: README文档 | 编写使用文档 | T29 |
| T34: 示例代码 | 编写示例 | T33 |

---

## 5.8 一周后MVP功能

**完成目标**: 能够对单只股票进行分析并给出交易建议

```python
from agent_integration import TradingAgentsGraph

# 一行代码完成分析
graph = TradingAgentsGraph(provider='minimax')  # 或 'deepseek'
result = graph.propagate('600519', '2024-05-10')

print(result)
# {
#     'decision': 'BUY',  # 或 'HOLD', 'SELL'
#     'confidence': 0.75,
#     'reasoning': '技术面看涨，新闻情绪正面...',
#     'risk_level': 'MEDIUM',
# }
```

---

## 5.9 后续扩展 (一周后)

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| **Week 2** | 完成全部13个智能体 + 完整辩论流程 | P0 |
| **Week 3** | 添加港股/美股数据支持 | P1 |
| **Week 4** | ChromaDB向量记忆集成 | P2 |
| **Week 5+** | 批量分析、历史回测、实盘接口 | P3 |

---

## 6. 数据流关键接口定义

### 6.1 统一数据接口 (interface.py)

```python
# agent_integration/dataflows/interface.py

from typing import Dict, List, Optional

def get_china_stock_data_unified(
    symbol: str,
    start_date: str,
    end_date: str,
    fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    统一的A股数据获取接口
    
    优先级:
    1. DuckDB缓存
    2. akshare实时
    3. baostock备用
    """
    
def get_stock_news_unified(
    symbol: str,
    market: str = 'china',
    limit: int = 20,
    include_sentiment: bool = True
) -> List[Dict]:
    """
    统一的股票新闻获取接口
    
    Returns:
        [{
            'title': str,
            'content': str,
            'source': str,  # 'eastmoney' | 'sina' | 'caixin' | 'google'
            'published_at': str,
            'sentiment': str,  # 'positive' | 'negative' | 'neutral'
            'sentiment_score': float,  # -1.0 ~ 1.0
        }]
    """
    
def get_china_fundamentals_unified(
    symbol: str,
    period: str = 'annual'  # 'annual' | 'quarter'
) -> Dict[str, Any]:
    """
    统一的A股基本面数据接口
    """
```

### 6.2 新闻数据结构

```python
# agent_integration/dataflows/news/schema.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    content: str
    source: str  # 新闻来源标识
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    symbols: Optional[List[str]] = None  # 关联股票
    sentiment: str = 'neutral'  # positive/negative/neutral
    sentiment_score: float = 0.0  # -1.0 ~ 1.0
    
@dataclass  
class StockNewsResult:
    """股票新闻结果"""
    symbol: str
    news: List[NewsItem]
    total_count: int
    fetched_at: datetime
    sources: List[str]  # 实际使用的来源
```

### 6.3 缓存Key规范

```python
# agent_integration/dataflows/cache/keys.py

CACHE_KEY_PREFIX = 'ta:'

class CacheKeys:
    """缓存Key生成器"""
    
    @staticmethod
    def market_data(symbol: str, date: str) -> str:
        """市场数据缓存"""
        return f"{CACHE_KEY_PREFIX}market:{symbol}:{date}"
    
    @staticmethod
    def fundamentals(symbol: str, period: str) -> str:
        """基本面数据缓存"""
        return f"{CACHE_KEY_PREFIX}fund:{symbol}:{period}"
    
    @staticmethod
    def news(symbol: str, date: str) -> str:
        """新闻缓存"""
        return f"{CACHE_KEY_PREFIX}news:{symbol}:{date}"
    
    @staticmethod
    def sentiment(symbol: str, date: str) -> str:
        """情感分析缓存"""
        return f"{CACHE_KEY_PREFIX}sentiment:{symbol}:{date}"

# TTL设置
class CacheTTL:
    MARKET_DATA = 300      # 5分钟
    FUNDAMENTALS = 86400   # 24小时
    NEWS = 300             # 5分钟
    SENTIMENT = 3600       # 1小时
```

---

## 6. 风险与注意事项

### 6.1 许可证风险

| 组件 | 许可证 | 风险 |
|------|--------|------|
| `tradingagents/graph/` | Apache 2.0 | ✅ 无风险 |
| `tradingagents/agents/` | Apache 2.0 | ✅ 无风险 |
| `tradingagents/llm_adapters/` | Apache 2.0 | ✅ 无风险 |
| `tradingagents/dataflows/` | Apache 2.0 | ✅ 无风险 |
| `app/` (FastAPI后端) | PROPRIETARY | ❌ 不可用 |

**建议**: 仅使用Apache 2.0许可的tradingagents/核心代码

### 6.2 技术风险

| 风险 | 缓解措施 |
|------|----------|
| LangChain版本冲突 | 使用虚拟环境隔离 |
| LLM API成本 | 添加使用量追踪和限额 |
| 新闻API稳定性 | 实现降级策略 (多源备份) |
| 响应延迟 | 添加超时和异步支持 |

### 6.3 数据质量

| 问题 | 解决方案 |
|------|----------|
| 新闻源覆盖不全 | 集成多个中文新闻源 |
| 情绪分析准确性 | 调优prompt或使用更好模型 |
| 实时性 | 添加缓存TTL控制 |

---

## 7. 依赖清单

### 7.1 新增Python依赖

```txt
# agent_integration/requirements.txt
langchain>=0.3.0
langgraph>=0.4.8
langchain-openai
langchain-anthropic
langchain-google-genai

# 新闻源
finnhub-python>=2.4.23
alpha_vantage>=2.3.0
requests>=2.28.0
beautifulsoup4>=4.12.0
feedparser>=6.0.0

# 向量存储
chromadb>=1.0.12

# 可选: 缓存
# redis>=6.2.0
# motor>=3.3.0 (async MongoDB)
```

### 7.2 现有依赖复用

```python
# 已在requirements.txt中，可直接使用
akshare>=1.17.86
baostock>=0.8.8
duckdb>=0.9.0
backtrader>=1.9.0
```

---

## 8. 成功标准

### 8.1 功能验收

- [ ] `TradingAgentsGraph` 可正常初始化
- [ ] 5个分析师可独立运行并返回报告
- [ ] 研究员可基于分析师报告生成论点
- [ ] 辩论流程可正常执行
- [ ] 最终交易建议可生成

### 8.2 集成验收

- [ ] 可调用现有DuckDB数据
- [ ] 可调用akshare/baostock数据
- [ ] 配置通过Settings统一管理
- [ ] 结果可存入数据库

### 8.3 性能验收

- [ ] 单股票分析 < 60秒 (使用缓存)
- [ ] 并发分析支持 >= 3个股票
- [ ] LLM Token使用可追踪

---

## 9. 后续扩展

### 9.1 短期 (1-2月)

- [ ] 实盘交易接口集成
- [ ] 实时数据推送
- [ ] Web界面增强

### 9.2 中期 (3-6月)

- [ ] 多模型对比 (DeepSeek vs GPT-4 vs Claude)
- [ ] 策略自适应学习
- [ ] 组合优化建议

### 9.3 长期 (6月+)

- [ ] 港股/美股市场覆盖
- [ ] 量化因子自动挖掘
- [ ] 风险预警系统

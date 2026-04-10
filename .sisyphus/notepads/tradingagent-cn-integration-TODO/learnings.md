# Day 2 Dataflow Core 实现笔记

## 已完成的实现 (T7-T11)

### T7: 新闻基类 (`agent_integration/dataflows/news/base.py`)
- **NewsItem**: 添加了 `published_at: datetime` 字段，支持多种日期格式自动解析
- **BaseNewsSource**: 定义抽象方法 `get_stock_news()` 和 `get_market_news()`
- 添加了 `to_dict()` 方法便于序列化

### T8: 东方财富新闻源 (`agent_integration/dataflows/news/eastmoney.py`)
- 使用 akshare 的 `ak.stock_news_em(symbol)` 获取个股新闻
- 列名映射: `新闻标题` -> `title`, `新闻内容` -> `content`, `发布时间` -> `published_at`, etc.
- 支持日期过滤和数量限制

### T9: 新闻聚合器 (`agent_integration/dataflows/news/aggregator.py`)
- 使用 ThreadPoolExecutor 并行获取多新闻源
- 按 URL 去重
- 按时间排序（最新在前）
- 返回 `StockNewsResult` 数据类

### T10: 情感分析器 (`agent_integration/dataflows/news/sentiment.py`)
- 基于词典的情感分析，不依赖 LLM
- POSITIVE_WORDS 和 NEGATIVE_WORDS 列表
- 支持强化词（大幅、明显等）和否定词（非、未等）
- score 范围 [-1.0, 1.0]

### T11: 股票数据适配器 (`agent_integration/dataflows/adapters/stock_adapter.py`)
- 优先使用 akshare 数据源
- 从本地数据库获取，不足时从 akshare 补充
- 懒加载 DatabaseManager 避免 schema 初始化问题
- 支持 `get_market_data()`, `get_stock_info()`, `get_fundamentals()`

## 已知问题
- DatabaseManager 单例在 schema.py 中有重复创建表的问题 (`portfolio_daily` already exists)
- 这是已有问题，不影响数据流模块功能

## 测试验证
```python
# T8: 东方财富新闻
EastMoneyNews().get_stock_news('600519')  # 返回 5 条新闻

# T9: 新闻聚合
NewsAggregator().get_stock_news('600519')  # 返回 StockNewsResult

# T10: 情感分析
SentimentAnalyzer().analyze_text('茅台股价上涨')  # (POSITIVE, 1.0)
SentimentAnalyzer().analyze_text('公司亏损严重')  # (NEGATIVE, -1.0)

# T11: 股票数据
StockDataAdapter().get_market_data('600519', '20240101', '20240510')  # 返回 83 条K线
```

## 实现模式参考
- 遵循项目现有的 import 结构
- 使用 `sys.path.insert(0, ...)` 导入项目模块
- DatabaseManager 单例模式
- StockFetcher 多数据源支持

## Day 3: Analyst Agents 实现笔记 (T12-T16)

### T12: Agent基类 (`agent_integration/agents/base.py`)
- **AgentConfig**: @dataclass with `name`, `role`, `llm_adapter`, `system_prompt`, `temperature`, `max_tokens`
- **BaseAgent**: ABC with abstract methods `_create_system_prompt()` and `_process_input()`
- **`run(inputs)`**: 主执行方法，返回 `{'success': bool, 'output': str, 'error': str}`
- **`_call_llm(messages)`**: 内部调用 `self._llm.chat(messages)`

### T13: MarketAnalyst (`agent_integration/agents/analysts/market_analyst.py`)
- **system prompt**: 技术分析师角色，关注K线、技术指标、趋势分析
- **`_format_price_data()`**: 将DataFrame格式化为文本表格（取最近20条）
- **`_format_indicators()`**: 格式化MA、MACD、RSI、KDJ、BOLL等技术指标
- **`analyze_with_data()`**: 使用实际数据进行完整分析

### T14: NewsAnalyst (`agent_integration/agents/analysts/news_analyst.py`)
- **system prompt**: 新闻分析师角色，关注新闻对股价影响
- **`_format_single_news()`**: 支持NewsItem和dict格式
- **`_format_news_list()`**: 格式化多条新闻（最多10条）
- **`_format_sentiment()`**: 格式化情感分析数据
- 支持 `NewsItem` 类型直接传入

### T15: FundamentalsAnalyst (`agent_integration/agents/analysts/fundamentals_analyst.py`)
- **system prompt**: 基本面分析师角色，关注财务、估值、成长性
- **`_format_financials()`**: 格式化盈利能力、ROE、毛利率等
- **`_format_valuation()`**: 格式化P/E、P/B、市值等估值指标
- **`_format_growth()`**: 格式化营收增长、利润增长等成长指标
- **`analyze_all()`**: 综合基本面分析

### T16: 测试验证
```python
# 测试所有Analyst创建和基本方法
MarketAnalyst(AgentConfig(name='market', llm_adapter=mock_llm)).run({...})
NewsAnalyst(AgentConfig(name='news', llm_adapter=mock_llm)).run({...})
FundamentalsAnalyst(AgentConfig(name='fund', llm_adapter=mock_llm)).run({...})
```

### 重要模式
- LLM适配器: `self._llm.chat(messages)` 接口
- 消息格式: `[{'role': 'user'/'assistant'/'system', 'content': '...'}]`
- AgentConfig: 使用@dataclass定义配置
- BaseAgent: ABC模式，强制子类实现 `_create_system_prompt()` 和 `_process_input()`

## Day 4: Researchers + Graph 实现笔记 (T17-T20)

### T17: BullResearcher (`agent_integration/agents/researchers/bull_researcher.py`)
- **system prompt**: 牛市研究员角色，关注做多论点
- **`research_bull_case()`**: 返回 `{bull_points, target_price, upside_potential, confidence}`
- **`find_supporting_signals()`**: 返回支撑信号列表
- **`research_with_reports()`**: 基于分析师报告研究做多论点

### T18: BearResearcher (`agent_integration/agents/researchers/bear_researcher.py`)
- **system prompt**: 熊市研究员角色，关注风险信号
- **`research_bear_case()`**: 返回 `{bear_points, risk_level, downside_risk, confidence}`
- **`find_risk_signals()`**: 返回风险信号列表
- **`research_with_reports()`**: 基于分析师报告研究做空论点

### T19: AgentState (`agent_integration/graph/state.py`)
- **TypedDict**: 定义状态结构，包含所有报告和决策字段
- **`create_initial_state()`**: 创建初始状态
- 字段: messages, company_of_interest, trade_date, market_report, news_report, fundamentals_report, bull_research, bear_research, investment_decision, risk_assessment, final_decision, confidence

### T20: TradingAgentsGraph (`agent_integration/graph/trading_graph.py`)
- **`__init__`**: 初始化LLM和所有分析师/研究员
- **`_run_analysts_parallel()`**: ThreadPoolExecutor并行运行分析师
- **`_run_researchers()`**: 运行牛市/熊市研究员
- **`_generate_final_decision()`**: 根据置信度生成决策
- **`propagate()`**: 主入口，运行完整工作流

### 决策逻辑
```
bull_conf > bear_conf + 0.2 → 买入
bear_conf > bull_conf + 0.2 → 卖出/观望
否则 → 观望
```

### 测试验证
```python
graph = TradingAgentsGraph(llm=mock_llm)
result = graph.propagate('600519', '2024-05-10')
# result = {final_decision, confidence, reports, bull_research, bear_research, state}
```

## Day 5: Managers + Trader 实现笔记 (T21-T25)

### T21: ResearchManager (`agent_integration/agents/managers/research_manager.py`)
- **BaseAgent**: 继承BaseAgent
- **`conduct_research()`**: 综合研究报告，返回 `{recommendation, reasoning, key_points, confidence}`
- **`synthesize_findings()`**: 综合多个研究发现

### T22: RiskManager (`agent_integration/agents/managers/risk_manager.py`)
- **BaseAgent**: 继承BaseAgent
- **`assess_risk()`**: 返回 `{risk_level, risk_score, risk_factors, stop_loss}`
- **`suggest_position_size()`**: LOW=0.3, MEDIUM=0.15, HIGH=0.0
- **`validate_trade()`**: 返回 (是否合规, 原因列表)

### T23: Trader (`agent_integration/traders/trader.py`)
- **standalone**: 不继承BaseAgent
- **`generate_trading_signal()`**: 生成交易信号 `{action, entry_price, stop_loss, take_profit, position_size, quantity, reasoning}`
- **`execute_buy/execute_sell()`**: 模拟执行（无broker时）
- **`get_position()`**: 获取持仓

### T24: SimpleDebator
- **跳过**: 可选任务

### T25: 端到端测试
完整工作流：
1. TradingAgentsGraph.propagate() → 分析师报告 + 研究论点
2. ResearchManager.conduct_research() → 投资建议
3. RiskManager.assess_risk() → 风险评估
4. Trader.generate_trading_signal() → 交易信号

交易信号示例：
```
action=BUY, entry=100.0, stop=95.0, take_profit=115.0
position_size=0.3, quantity=300, reasoning=基于买入决策...
```

## Day 6-7: Integration + Documentation (T26-T34)

### T26: ConfigAdapter (`agent_integration/adapters/config_adapter.py`)
- **`get_agent_config()`**: 返回 `{providers, default_provider, default_model, temperature}`
- **`get_llm_config(provider)`**: 返回 `{provider, model, temperature, api_key}`
- **`get_data_config()`**: 返回数据源配置

### T27: ResultAdapter (`agent_integration/adapters/result_adapter.py`)
- **`save_analysis_result()`**: 保存到DuckDB `agent_analysis_results` 表
- **`load_analysis_result()`**: 通过run_id加载
- **`get_analysis_history()`**: 获取分析历史

### T28: Flask API (`agent_integration/api/analyzer.py`)
- **`analyze_stock(symbol, trade_date)`**: 主入口函数
- **`get_analysis_history(symbol, limit)`**: 获取历史
- **`health_check()`**: 健康检查
- 使用TradingAgentsGraph内部

### T30: Token Tracking
- **`get_token_stats()`**: 在 `llm_adapters/base.py` 中添加
- 返回详细统计: `{total_tokens, total_cost, by_model, recent_usages}`

### T33: README (`agent_integration/README.md`)
- 架构图
- 安装说明
- 快速开始
- API参考
- 目录结构

### T34: Examples
- **`examples/basic_usage.py`**: 单股票分析示例
- **`examples/batch_analysis.py`**: 批量分析示例

## 已创建的新文件
- `agent_integration/adapters/result_adapter.py`
- `agent_integration/api/analyzer.py`
- `agent_integration/api/__init__.py`
- `agent_integration/README.md`
- `agent_integration/examples/basic_usage.py`
- `agent_integration/examples/batch_analysis.py`
- `agent_integration/examples/__init__.py`

## 已知问题
- DatabaseManager 单例有schema重复创建问题 (`portfolio_daily` already exists)

## Week 2: Full Debate Flow

### New Files Created:
- `agent_integration/agents/risk_mgmt/__init__.py`
- `agent_integration/agents/risk_mgmt/conservative_debator.py`
- `agent_integration/agents/risk_mgmt/neutral_debator.py`
- `agent_integration/agents/risk_mgmt/aggressive_debator.py`
- `agent_integration/agents/risk_mgmt/debate_aggregator.py`

### Classes Implemented:

#### ConservativeDebater
- 保守型风险辩论者
- 强调风险控制，建议低仓位
- `debate()` → {stance, arguments, risk_points, confidence, recommended_position}

#### NeutralDebater  
- 中性风险辩论者
- 平衡多空观点，适中仓位
- `debate()` → same signature

#### AggressiveDebater
- 激进型风险辩论者
- 强调投资机会，高仓位
- `debate()` → same signature

#### DebateAggregator
- 协调三方辩论
- `run_debate()` 并行运行三个debater
- 聚合观点得出最终风险等级

### Updated Files:
- `agent_integration/graph/trading_graph.py` - 添加辩论阶段
- `agent_integration/api/analyzer.py` - 添加debate_round字段

### Risk Level Rules:
- 2+ agree HIGH → HIGH (position=0.0)
- 2+ agree LOW → LOW (position=0.3)  
- otherwise → MEDIUM (position=0.15)

### Verification Results:
```
✓ DebateAggregator.run_debate() returns 3 views
✓ TradingAgentsGraph.propagate() includes debate_result
✓ debate_result contains: conservative_view, neutral_view, aggressive_view, final_risk_level, recommended_position
```

## Week 3: HK/US Stock Data Support

### New Files Created:
- `agent_integration/dataflows/markets/__init__.py`
- `agent_integration/dataflows/markets/hk_stocks.py`
- `agent_integration/dataflows/markets/us_stocks.py`
- `agent_integration/dataflows/markets/router.py`

### Classes Implemented:

#### HKStockData
- `get_historical_data(symbol, start_date, end_date)` - 港股历史K线
- `get_realtime_data(symbol)` - 港股实时行情
- `get_stock_info(symbol)` - 港股基本信息
- `search_stocks(keyword)` - 搜索港股
- Symbol format: '00700' or 'HK.00700'

#### USStockData
- `get_historical_data(symbol, start_date, end_date)` - 美股历史K线
- `get_realtime_data(symbol)` - 美股实时行情
- `get_stock_info(symbol)` - 美股基本信息
- `search_stocks(keyword)` - 搜索美股
- Symbol format: 'AAPL' or 'US.AAPL'

#### MarketRouter
- `detect_market(symbol)` - 自动识别市场 (china/hk/us)
- `get_market_data(symbol, start_date, end_date)` - 统一数据接口
- `get_realtime_data(symbol)` - 统一实时数据
- `get_stock_info(symbol)` - 统一股票信息

### Updated Files:
- `agent_integration/dataflows/adapters/stock_adapter.py` - 添加MarketRouter支持
- `agent_integration/dataflows/news/aggregator.py` - 添加市场检测

### Symbol Formats:
- A股: '600519', '000001', '300750'
- 港股: '00700', 'HK.00700'
- 美股: 'AAPL', 'US.AAPL'

### Known Issues:
- Symbol detection edge cases: '00700' detected as china (matches digit pattern)
- 'AAPL' detected as hk (4 chars)
- HK/US news sources return empty (需要额外新闻源支持)

## Week 4: ChromaDB Vector Memory

### New Files Created:
- `agent_integration/memory/__init__.py`
- `agent_integration/memory/vector_store.py`
- `agent_integration/memory/memory_manager.py`
- `agent_integration/memory/config.py`

### Classes Implemented:

#### VectorStore
- ChromaDB wrapper with graceful fallback
- `add()` - Add vectors
- `search()` - Similarity search
- `get_by_filter()` - Get by metadata filter
- `delete()` - Delete vectors
- `is_available()` - Check if ChromaDB installed

#### MemoryManager
- High-level memory management
- `save_analysis_result()` - Save analysis to vector DB
- `search_related()` - Search related memories
- `get_history()` - Get analysis history
- `clear_old()` - Clear old memories

#### MemoryConfig
- Configuration class with environment variable support
- `PERSIST_DIRECTORY`, `COLLECTION_ANALYSIS`, `COLLECTION_NEWS`
- `load_from_env()` - Load from environment variables

### Updated Files:
- `graph/trading_graph.py` - Added memory_manager, include_memory_context
- `api/analyzer.py` - Added include_memory parameter

### Key Features:
- ChromaDB is optional - graceful fallback if not installed
- Memory integration in TradingAgentsGraph.propagate()
- Memory context passed to/from propagate() results

### Verification Results:
```
✓ Memory modules imported
✓ CHROMADB_AVAILABLE = False (ChromaDB not installed)
✓ VectorStore.is_available(): False
✓ MemoryManager.is_available(): False
✓ TradingAgentsGraph accepts memory_manager parameter
✓ analyze_stock signature includes include_memory
```

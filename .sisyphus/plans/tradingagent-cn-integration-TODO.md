# TradingAgents-CN 集成完整TODO清单

> **生成时间**: 2026-03-29
> **版本**: 1.0 (一周紧凑版)

---

## 执行TODO

### Week 1: MVP交付

---

## Day 1: 项目搭建 + LLM适配器

### T1: 创建项目目录结构

**文件**: `agent_integration/`
```
agent_integration/
├── __init__.py
├── llm_adapters/
│   ├── __init__.py
│   ├── base.py
│   ├── factory.py
│   ├── deepseek.py
│   └── minimax.py
├── dataflows/
│   ├── __init__.py
│   ├── news/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── eastmoney.py
│   │   ├── aggregator.py
│   │   └── sentiment.py
│   └── adapters/
│       ├── __init__.py
│       └── stock_adapter.py
├── agents/
│   ├── __init__.py
│   ├── base.py
│   ├── analysts/
│   │   ├── __init__.py
│   │   ├── market_analyst.py
│   │   ├── news_analyst.py
│   │   └── fundamentals_analyst.py
│   ├── researchers/
│   │   ├── __init__.py
│   │   ├── bull_researcher.py
│   │   └── bear_researcher.py
│   └── managers/
│       ├── __init__.py
│       ├── research_manager.py
│       └── risk_manager.py
├── graph/
│   ├── __init__.py
│   └── trading_graph.py
└── adapters/
    ├── __init__.py
    └── config_adapter.py
```

**验收标准**:
- [x] `agent_integration/__init__.py` 可正常导入
- [x] 子模块全部创建空文件

---

### T2: LLM适配器基类

**文件**: `agent_integration/llm_adapters/base.py`

**实现内容**:
```python
# 1. TokenTracker类
class TokenTracker:
    - track(usage_metadata, model)
    - get_stats()
    - reset()
    - PRICE_PER_MILLION = {minimax: {input: 0.5, output: 1.5}, ...}

# 2. OpenAICompatibleBase类
class OpenAICompatibleBase(BaseChatModel):
    - __init__(model, api_key, temperature, max_tokens, timeout, max_retries, token_tracker)
    - _generate() - 同步生成
    - _agenerate() - 异步生成
    - _call_with_retry() - 带重试的API调用
    - _convert_messages() - 消息格式转换
    - _convert_response() - 响应格式转换
    - get_token_usage()
```

**验收标准**:
- [x] `TokenTracker` 可正常统计token使用
- [x] `OpenAICompatibleBase` 继承自 `BaseChatModel`
- [x] 支持同步和异步调用

---

### T3: LLM工厂函数

**文件**: `agent_integration/llm_adapters/factory.py`

**实现内容**:
```python
# 1. create_llm_by_provider()
# 2. create_llm_by_model()
# 3. create_llm_with_fallback()
# 4. get_global_token_tracker()
# 5. reset_global_token_tracker()

# PROVIDER_MAP = {
#     'deepseek': ChatDeepSeek,
#     'minimax': ChatMiniMax,
# }

# MODEL_PROVIDER_MAP = {
#     'deepseek-chat': 'deepseek',
#     'M2': 'minimax',
#     'M2.1': 'minimax',
# }
```

**验收标准**:
- [x] `create_llm_by_provider('minimax', 'M2.1')` 返回有效LLM
- [x] `create_llm_by_model('deepseek-chat')` 自动识别提供商

---

### T4: DeepSeek适配器

**文件**: `agent_integration/llm_adapters/deepseek.py`

**实现内容**:
```python
class ChatDeepSeek(OpenAICompatibleBase):
    provider_name = "deepseek"
    default_model = "deepseek-chat"
    API_BASE = "https://api.deepseek.com/v1"
```

**验收标准**:
- [x] `create_llm_by_provider('deepseek', 'deepseek-chat')` 可用
- [x] API Key从环境变量 `DEEPSEEK_API_KEY` 读取

---

### T5: MiniMax适配器

**文件**: `agent_integration/llm_adapters/minimax.py`

**实现内容**:
```python
class ChatMiniMax(OpenAICompatibleBase):
    provider_name = "minimax"
    default_model = "M2"
    API_BASE = "https://api.minimax.io/v1"
    
    # 需要 group_id 参数
```

**验收标准**:
- [x] `create_llm_by_provider('minimax', 'M2.1', group_id='xxx')` 可用
- [x] API Key从环境变量 `MINIMAX_API_KEY` 读取
- [x] Group ID从环境变量 `MINIMAX_GROUP_ID` 读取

---

### T6: LLM调用测试

**验证命令**:
```python
from agent_integration.llm_adapters import create_llm_by_provider
from langchain.schema import HumanMessage

llm = create_llm_by_provider('minimax', 'M2.1')
response = llm([HumanMessage(content="你好")])
print(response.content)  # 应返回中文响应
```

**验收标准**:
- [x] MiniMax API调用成功
- [x] Token使用被追踪

---

## Day 2: 数据流核心

### T7: 新闻基类

**文件**: `agent_integration/dataflows/news/base.py`

**实现内容**:
```python
class Sentiment(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

@dataclass
class NewsItem:
    title: str
    content: str
    source: str
    url: str
    published_at: datetime
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_score: float = 0.0

@dataclass
class StockNewsResult:
    symbol: str
    news: List[NewsItem]
    total_count: int
    fetched_at: datetime
    sources: List[str]

class BaseNewsSource(ABC):
    name: str
    base_url: str
    
    @abstractmethod
    def get_stock_news(self, symbol, limit, start_date) -> List[NewsItem]
    
    @abstractmethod
    def get_market_news(self, market, limit, start_date) -> List[NewsItem]
```

**验收标准**:
- [x] `NewsItem` 可正常创建
- [x] `BaseNewsSource` 可作为基类使用

---

### T8: 东方财富新闻源

**文件**: `agent_integration/dataflows/news/eastmoney.py`

**实现内容**:
```python
class EastMoneyNews(BaseNewsSource):
    name = 'eastmoney'
    
    def get_stock_news(self, symbol, limit=20, start_date=None) -> List[NewsItem]
        # 1. 搜索接口获取新闻
        # 2. 公告接口获取公告
        # 3. 解析JSON返回NewsItem列表
    
    def get_market_news(self, market, limit, start_date) -> List[NewsItem]
```

**验收标准**:
- [x] `EastMoneyNews().get_stock_news('600519')` 返回新闻列表
- [x] 返回结果包含 title, content, source, url, published_at

---

### T9: 新闻聚合器

**文件**: `agent_integration/dataflows/news/aggregator.py`

**实现内容**:
```python
class NewsAggregator:
    def __init__(self, sources=['eastmoney']):
        self.sources = {...}
        self.default_sources = sources
    
    def get_stock_news(
        self, 
        symbol, 
        sources=None, 
        limit=20,
        include_sentiment=True
    ) -> StockNewsResult
        # 1. 并行调用多个新闻源
        # 2. 去重 (按URL)
        # 3. 情感分析
        # 4. 按时间排序
    
    def get_market_news(self, market, limit) -> List[NewsItem]
```

**验收标准**:
- [x] `NewsAggregator().get_stock_news('600519')` 返回StockNewsResult
- [x] 多个源可并行获取
- [x] 自动去重

---

### T10: 情感分析模块

**文件**: `agent_integration/dataflows/news/sentiment.py`

**实现内容**:
```python
# 正面词表
POSITIVE_WORDS = ['上涨', '涨停', '突破', '增长', '超预期', ...]

# 负面词表
NEGATIVE_WORDS = ['下跌', '跌停', '亏损', '风险', '暴雷', ...]

class SentimentAnalyzer:
    def __init__(self, use_llm=False, llm_adapter=None):
        self.use_llm = use_llm
    
    def analyze(self, text) -> Tuple[Sentiment, float]:
        # 词典模式: 匹配正/负面词，计算分数
        # LLM模式: 调用LLM分析 (可选)
```

**验收标准**:
- [x] `"茅台股价上涨"` 分析为正面 (score > 0)
- [x] `"茅台股价跌停"` 分析为负面 (score < 0)
- [x] `SentimentAnalyzer(use_llm=True)` 使用LLM分析

---

### T11: 股票数据适配器

**文件**: `agent_integration/dataflows/adapters/stock_adapter.py`

**实现内容**:
```python
from data.fetchers.stock_fetcher import StockFetcher
from database.db_manager import DatabaseManager

class StockDataAdapter:
    def __init__(self):
        self._fetcher = StockFetcher()
        self._db = DatabaseManager.get_instance()
    
    def get_market_data(self, symbol, start_date, end_date) -> Dict:
        """获取K线数据"""
        # 优先从DuckDB获取
        # 不足时从akshare补充
    
    def get_stock_info(self, symbol) -> Dict:
        """获取股票基本信息"""
    
    def get_fundamentals(self, symbol, period) -> Dict:
        """获取基本面数据"""
```

**验收标准**:
- [x] `StockDataAdapter().get_market_data('600519', '20240101', '20240510')` 返回数据
- [x] 数据格式与TradingAgents兼容

---

## Day 3: 分析师智能体

### T12: Agent基类

**文件**: `agent_integration/agents/base.py`

**实现内容**:
```python
@dataclass
class AgentConfig:
    name: str
    role: str
    goal: str
    backstory: str
    llm: Optional[BaseChatModel] = None
    verbose: bool = False

class BaseAgent(ABC):
    def __init__(self, config: AgentConfig):
        self.config = config
        self._history = []
    
    @abstractmethod
    def _create_system_prompt(self) -> str
    
    @abstractmethod
    def _process_input(self, inputs: Dict) -> str
    
    def run(self, inputs: Dict) -> Dict:
        # 1. 创建系统提示
        # 2. 处理输入
        # 3. 调用LLM
        # 4. 返回结果
```

**验收标准**:
- [x] `BaseAgent` 可正常继承
- [x] `run()` 方法返回 `{success, output, agent}`

---

### T13: MarketAnalyst

**文件**: `agent_integration/agents/analysts/market_analyst.py`

**实现内容**:
```python
class MarketAnalyst(BaseAgent):
    def _create_system_prompt(self) -> str:
        # 返回技术分析师的系统提示
    
    def _process_input(self, inputs: Dict) -> str:
        # inputs: {symbol, stock_name, price_data, indicators, trade_date}
        # 返回格式化的用户提示

    def _format_price_data(self, data: List[Dict]) -> str:
        # 格式化K线数据
    
    def _format_indicators(self, indicators: Dict) -> str:
        # 格式化技术指标
```

**验收标准**:
- [x] `MarketAnalyst(AgentConfig(name='xxx', llm=llm)).run({...})` 正常执行
- [x] 返回技术分析报告

---

### T14: NewsAnalyst

**文件**: `agent_integration/agents/analysts/news_analyst.py`

**实现内容**:
```python
class NewsAnalyst(BaseAgent):
    def _create_system_prompt(self) -> str:
        # 返回新闻分析师的系统提示
    
    def _process_input(self, inputs: Dict) -> str:
        # inputs: {symbol, stock_name, news: List[NewsItem], trade_date}
```

**验收标准**:
- [x] 可处理NewsAggregator返回的数据
- [x] 返回新闻情绪分析报告

---

### T15: FundamentalsAnalyst

**文件**: `agent_integration/agents/analysts/fundamentals_analyst.py`

**实现内容**:
```python
class FundamentalsAnalyst(BaseAgent):
    def _create_system_prompt(self) -> str:
        # 返回基本面分析师的系统提示
    
    def _process_input(self, inputs: Dict) -> str:
        # inputs: {symbol, stock_name, financials, industry_avg}
```

**验收标准**:
- [x] 可处理财务数据
- [x] 返回基本面分析报告

---

### T16: 分析师测试

**验证命令**:
```python
from agent_integration.agents import MarketAnalyst, NewsAnalyst, FundamentalsAnalyst
from agent_integration.agents.base import AgentConfig
from agent_integration.llm_adapters import create_llm_by_provider

llm = create_llm_by_provider('minimax', 'M2.1')

market = MarketAnalyst(AgentConfig(name='market', llm=llm))
result = market.run({
    'symbol': '600519',
    'stock_name': '贵州茅台',
    'price_data': [...],  # 从StockDataAdapter获取
    'indicators': {...},
    'trade_date': '2024-05-10'
})

print(result['success'])  # True
print(result['output'][:100])  # 分析报告前100字
```

**验收标准**:
- [x] 3个分析师都能正常运行
- [x] 输出结构化分析报告

---

## Day 4: 研究员 + Graph

### T17: BullResearcher

**文件**: `agent_integration/agents/researchers/bull_researcher.py`

**实现内容**:
```python
class BullResearcher(BaseAgent):
    def _create_system_prompt(self) -> str:
        return """你是一位专业的看涨研究员...
        构建3-5个看涨理由...
        目标价和上涨空间...
        """
    
    def _process_input(self, inputs: Dict) -> str:
        # inputs: {symbol, analyst_reports: {market, news, fundamentals}}
```

**验收标准**:
- [x] 基于分析师报告生成看涨论点
- [x] 包含目标价和催化剂

---

### T18: BearResearcher

**文件**: `agent_integration/agents/researchers/bear_researcher.py`

**实现内容**:
```python
class BearResearcher(BaseAgent):
    # 与BullResearcher类似，但立场为空头
```

**验收标准**:
- [x] 基于分析师报告生成看跌论点
- [x] 包含下行风险

---

### T19: AgentState定义

**文件**: `agent_integration/graph/state.py`

**实现内容**:
```python
class AgentState(TypedDict):
    messages: HumanMessage
    company_of_interest: str
    trade_date: str
    
    # 分析报告
    market_report: str
    fundamentals_report: str
    news_report: str
    
    # 研究论点
    bull_research: str
    bear_research: str
    
    # 决策
    investment_decision: str
    risk_assessment: str
    
    # 最终结果
    final_decision: str
    confidence: float
```

**验收标准**:
- [x] `AgentState` 可用于LangGraph

---

### T20: TradingAgentsGraph

**文件**: `agent_integration/graph/trading_graph.py`

**实现内容**:
```python
class TradingAgentsGraph:
    def __init__(
        self,
        llm=None,
        selected_analysts=['market', 'news', 'fundamentals'],
        debug=False
    ):
        # 1. 初始化LLM
        # 2. 创建分析师
        # 3. 创建研究员
        # 4. 构建LangGraph
    
    def propagate(self, company_of_interest, trade_date) -> Dict:
        # 1. 并行运行分析师
        # 2. 运行研究员
        # 3. 生成决策
        # 4. 返回最终结果
```

**验收标准**:
- [x] `TradingAgentsGraph(provider='minimax')` 可初始化
- [x] `graph.propagate('600519', '2024-05-10')` 返回分析结果

---

## Day 5: 管理器 + 简化决策

### T21: ResearchManager

**文件**: `agent_integration/agents/managers/research_manager.py`

**实现内容**:
```python
class ResearchManager(BaseAgent):
    def _create_system_prompt(self) -> str:
        return """你是投资研究总监...
        整合看涨/看跌论点...
        给出最终投资决策: 买入/持有/卖出...
        """
    
    def _process_input(self, inputs: Dict) -> str:
        # inputs: {bull_research, bear_research}
```

**验收标准**:
- [x] 整合多空论点
- [x] 给出明确的 `decision`

---

### T22: RiskManager

**文件**: `agent_integration/agents/managers/risk_manager.py`

**实现内容**:
```python
class RiskManager(BaseAgent):
    def _create_system_prompt(self) -> str:
        return """你是风险管理总监...
        评估投资风险...
        制定风控策略...
        """
    
    def _process_input(self, inputs: Dict) -> str:
        # inputs: {investment_decision, ...}
```

**验收标准**:
- [x] 生成风险评级
- [x] 制定止损/止盈策略

---

### T23: Trader

**文件**: `agent_integration/agents/trader/trader.py`

**实现内容**:
```python
class Trader(BaseAgent):
    def _create_system_prompt(self) -> str:
        return """你是专业交易员...
        生成最终交易指令...
        """
    
    def _process_input(self, inputs: Dict) -> str:
        # inputs: {decision, risk_strategy, current_price}
```

**验收标准**:
- [x] 生成交易信号: BUY/SELL/HOLD
- [x] 包含入场点位、仓位、止损止盈

---

### T24: 简化辩论 (可选，如果时间充裕)

**文件**: `agent_integration/agents/risk_mgmt/simple_debator.py`

**合并3个debator为1个**:
```python
class SimpleDebator(BaseAgent):
    # 同时输出保守、中性、激进观点
```

**验收标准**:
- [x] 一个Agent输出三种观点

---

### T25: 端到端测试

**验证命令**:
```python
from agent_integration import TradingAgentsGraph

graph = TradingAgentsGraph(provider='minimax')
result = graph.propagate('600519', '2024-05-10')

print(result)
# {
#     'final_decision': 'BUY',
#     'confidence': 0.75,
#     'trading_signal': {
#         'action': 'BUY',
#         'entry_price': 1700.0,
#         'stop_loss': 1600.0,
#         'take_profit': 1850.0,
#         'position_size': 0.3
#     },
#     'reports': {
#         'market': '...',
#         'news': '...',
#         'fundamentals': '...'
#     }
# }
```

**验收标准**:
- [x] 完整流程运行成功
- [x] 返回结构化结果

---

## Day 6: 集成 + 适配

### T26: 配置适配器

**文件**: `agent_integration/adapters/config_adapter.py`

**实现内容**:
```python
from config.settings import Settings

class ConfigAdapter:
    # LLM配置
    LLM_PROVIDER = Settings.LLM_PROVIDER
    LLM_MODEL = Settings.LLM_MODEL
    LLM_API_KEY = Settings.LLM_API_KEY
    
    # 数据源配置
    DATA_SOURCE = Settings.DATA_SOURCE
    
    # 缓存配置
    USE_REDIS = Settings.USE_REDIS_CACHE
```

**验收标准**:
- [x] 从Settings读取配置
- [x] 支持环境变量覆盖

---

### T27: 结果存储适配器

**文件**: `agent_integration/adapters/result_adapter.py`

**实现内容**:
```python
class ResultAdapter:
    def __init__(self):
        self._db = DatabaseManager.get_instance()
    
    def save_analysis_result(self, symbol, trade_date, result) -> str:
        """保存分析结果到DuckDB"""
        # 存入 backtest_run 或新建表
    
    def load_analysis_result(self, run_id: str) -> Dict:
        """加载分析结果"""
```

**验收标准**:
- [x] 分析结果可存入DuckDB
- [x] 可通过run_id加载

---

### T28: Flask API路由

**文件**: `dashboard/agent_api.py` 或 `agent_integration/api.py`

**实现内容**:
```python
from flask import Blueprint, request, jsonify

agent_bp = Blueprint('agent', __name__, url_prefix='/api/agent')

@agent_bp.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    symbol = data.get('symbol')
    trade_date = data.get('trade_date')
    
    graph = TradingAgentsGraph(provider='minimax')
    result = graph.propagate(symbol, trade_date)
    
    return jsonify(result)

@agent_bp.route('/history', methods=['GET'])
def history():
    # 返回历史分析记录
```

**验收标准**:
- [x] POST `/api/agent/analyze` 可用
- [x] 返回JSON格式结果

---

### T29: 集成测试

**验证命令**:
```bash
# 启动Flask应用
python dashboard/app.py

# 测试API
curl -X POST http://localhost:5001/api/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519", "trade_date": "2024-05-10"}'
```

**验收标准**:
- [x] API正常响应
- [x] 结果存入数据库

---

## Day 7: 优化 + 文档

### T30: Token追踪优化

**实现内容**:
- 添加每日/每周Token使用报表
- 添加成本预警 (超过阈值提醒)

**验收标准**:
- [ ] 可查看Token使用统计

---

### T31: 缓存优化 (可选)

**实现内容**:
- 添加Redis缓存 (如果可用)
- 缓存新闻和分析结果

**验收标准**:
- [ ] 相同请求在TTL内返回缓存

---

### T32: 异常处理完善

**实现内容**:
- API超时处理
- LLM降级处理
- 网络错误重试

**验收标准**:
- [ ] 异常情况不崩溃
- [ ] 返回有意义的错误信息

---

### T33: README文档

**文件**: `agent_integration/README.md`

**内容**:
```markdown
# TradingAgents-CN 集成模块

## 快速开始

```python
from agent_integration import TradingAgentsGraph

graph = TradingAgentsGraph(provider='minimax')
result = graph.propagate('600519', '2024-05-10')
```

## 环境变量

```bash
MINIMAX_API_KEY=xxx
MINIMAX_GROUP_ID=xxx
DEEPSEEK_API_KEY=xxx
```

## API文档

...
```

**验收标准**:
- [ ] README包含安装说明
- [ ] 包含使用示例

---

### T34: 示例代码

**文件**: `agent_integration/examples/`

```
examples/
├── basic_usage.py      # 基础使用
├── batch_analysis.py   # 批量分析
├── flask_integration.py # Flask集成
└── backtest_integration.py # 回测集成
```

**验收标准**:
- [ ] 每个示例可独立运行

---

## 验收检查清单

### 功能验收

- [x] T1: 目录结构创建
- [x] T2-T6: LLM适配器可用
- [x] T7-T11: 数据流可获取新闻和K线
- [x] T12-T16: 3个分析师正常工作
- [x] T17-T20: Graph可编排执行
- [x] T21-T25: 完整流程可运行
- [x] T26-T29: Flask API可用
- [x] T33-T34: 文档完整 ✅

### 集成验收

- [x] Settings配置正确读取
- [x] 分析结果存入DuckDB
- [x] Flask API正常响应

### 性能验收

- [ ] 单股票分析 < 60秒
- [x] Token使用被追踪
- [x] 异常情况有错误处理

---

## 代码位置汇总

```
agent_integration/
├── __init__.py
├── README.md
├── llm_adapters/
│   ├── __init__.py
│   ├── base.py          # T2
│   ├── factory.py       # T3
│   ├── deepseek.py      # T4
│   └── minimax.py       # T5
├── dataflows/
│   ├── __init__.py
│   ├── news/
│   │   ├── __init__.py
│   │   ├── base.py      # T7
│   │   ├── eastmoney.py # T8
│   │   ├── aggregator.py # T9
│   │   └── sentiment.py  # T10
│   └── adapters/
│       ├── __init__.py
│       └── stock_adapter.py # T11
├── agents/
│   ├── __init__.py
│   ├── base.py          # T12
│   ├── analysts/
│   │   ├── __init__.py
│   │   ├── market_analyst.py      # T13
│   │   ├── news_analyst.py        # T14
│   │   └── fundamentals_analyst.py # T15
│   ├── researchers/
│   │   ├── __init__.py
│   │   ├── bull_researcher.py    # T17
│   │   └── bear_researcher.py    # T18
│   └── managers/
│       ├── __init__.py
│       ├── research_manager.py    # T21
│       └── risk_manager.py        # T22
├── graph/
│   ├── __init__.py
│   └── trading_graph.py # T19, T20
├── traders/
│   ├── __init__.py
│   └── trader.py        # T23
├── adapters/
│   ├── __init__.py
│   ├── config_adapter.py # T26
│   └── result_adapter.py # T27
└── examples/
    ├── __init__.py
    ├── basic_usage.py
    ├── batch_analysis.py
    └── flask_integration.py
```

---

## 下一步

完成Week 1 MVP后，可继续:

| Week | 内容 |
|------|------|
| Week 2 | 完成全部13个智能体 + 完整辩论流程 |
| Week 3 | 添加港股/美股数据支持 |
| Week 4 | ChromaDB向量记忆集成 |
| Week 5+ | 批量分析、历史回测、实盘接口 |

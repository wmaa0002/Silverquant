# Agent Integration 模块

A股量化交易智能体分析系统 - 基于多智能体协作的股票分析框架。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    TradingAgentsGraph                        │
│                   (工作流编排器)                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   Market    │  │   News      │  │Fundamentals │      │
│  │  Analyst    │  │  Analyst    │  │  Analyst    │      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
│         │                 │                 │              │
│         └─────────────────┼─────────────────┘              │
│                           ▼                                │
│                   ┌─────────────────┐                     │
│                   │  Bull/Bear      │                     │
│                   │  Researchers     │                     │
│                   └────────┬────────┘                     │
│                            │                               │
│         ┌─────────────────┼─────────────────┐             │
│         ▼                 ▼                 ▼             │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐       │
│  │  Research   │   │   Risk    │   │   Trader   │       │
│  │  Manager    │   │  Manager  │   │            │       │
│  └────────────┘   └────────────┘   └────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## 安装

```bash
# 克隆项目
cd 股票策略

# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export DEEPSEEK_API_KEY=your_api_key
```

## 快速开始

### 1. 使用API分析股票

```python
from agent_integration.api.analyzer import analyze_stock

# 分析单只股票
result = analyze_stock('600519', '2024-05-10')

print(f"决策: {result['final_decision']}")
print(f"置信度: {result['confidence']}")
print(f"交易信号: {result['trading_signal']}")
```

### 2. 使用TradingAgentsGraph

```python
from agent_integration.graph.trading_graph import TradingAgentsGraph
from agent_integration.llm_adapters.factory import create_llm_by_provider

# 创建LLM适配器
llm = create_llm_by_provider('deepseek', 'deepseek-chat', api_key='your_key')

# 创建工作流图
graph = TradingAgentsGraph(llm=llm)

# 运行分析
result = graph.propagate('600519', '2024-05-10')

print(result['final_decision'])
print(result['confidence'])
```

### 3. 使用分析师

```python
from agent_integration.agents.analysts.market_analyst import MarketAnalyst
from agent_integration.agents.base import AgentConfig

# 创建分析师
config = AgentConfig(name='market', role='market_analyst', llm_adapter=llm)
analyst = MarketAnalyst(config)

# 分析
result = analyst.analyze_with_data('600519', price_data, indicators)
```

## 核心组件

### 分析师 (Analysts)

| 类 | 说明 |
|---|---|
| `MarketAnalyst` | 技术分析：K线形态、均线、MACD、RSI等 |
| `NewsAnalyst` | 新闻分析：情感分析、事件影响评估 |
| `FundamentalsAnalyst` | 基本面分析：财务指标、估值、成长性 |

### 研究员 (Researchers)

| 类 | 说明 |
|---|---|
| `BullResearcher` | 牛市研究员：寻找做多论点 |
| `BearResearcher` | 熊市研究员：识别风险信号 |

### 经理 (Managers)

| 类 | 说明 |
|---|---|
| `ResearchManager` | 研究经理：综合研究成果 |
| `RiskManager` | 风控经理：评估风险、建议仓位 |

### 交易执行

| 类 | 说明 |
|---|---|
| `Trader` | 交易执行器：生成交易信号 |

## 配置

### ConfigAdapter

```python
from agent_integration.adapters.config_adapter import ConfigAdapter

config = ConfigAdapter()

# 获取LLM配置
llm_cfg = config.get_llm_config('deepseek')

# 获取数据源配置
data_cfg = config.get_data_config()

# 获取数据库配置
db_cfg = config.get_database_config()
```

### 环境变量

| 变量 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API密钥 |
| `MINIMAX_API_KEY` | MiniMax API密钥 |
| `TUSHARE_TOKEN` | Tushare Token |

## API参考

### analyze_stock(symbol, trade_date)

分析指定股票。

**参数：**
- `symbol`: 股票代码，如 '600519'
- `trade_date`: 交易日期，如 '2024-05-10'

**返回：**
```python
{
    'success': bool,
    'run_id': str,
    'symbol': str,
    'trade_date': str,
    'final_decision': str,  # 买入/观望/卖出
    'confidence': float,
    'trading_signal': {
        'action': str,
        'entry_price': float,
        'stop_loss': float,
        'take_profit': float,
        'position_size': float,
        'quantity': int
    },
    'reports': {...},
    'bull_research': str,
    'bear_research': str
}
```

### get_analysis_history(symbol=None, limit=10)

获取分析历史。

### health_check()

健康检查。

## 交易信号规则

| 风险等级 | 仓位 | 止损比例 |
|---|---|---|
| LOW | 30% | 5% |
| MEDIUM | 15% | 8% |
| HIGH | 0% | 10% |

## 数据流

1. **数据采集**：通过 `StockDataAdapter` 获取K线数据、新闻、基本面数据
2. **并行分析**：分析师（Market/News/Fundamentals）并行分析
3. **研究综合**：研究员（Bull/Bear）综合分析报告
4. **决策生成**：ResearchManager综合多空观点
5. **风险评估**：RiskManager评估风险等级
6. **信号生成**：Trader生成最终交易信号

## 目录结构

```
agent_integration/
├── adapters/           # 适配器
│   ├── config_adapter.py
│   └── result_adapter.py
├── agents/            # 智能体
│   ├── base.py
│   ├── analysts/      # 分析师
│   │   ├── market_analyst.py
│   │   ├── news_analyst.py
│   │   └── fundamentals_analyst.py
│   ├── researchers/   # 研究员
│   │   ├── bull_researcher.py
│   │   └── bear_researcher.py
│   └── managers/     # 经理
│       ├── research_manager.py
│       └── risk_manager.py
├── dataflows/         # 数据流
│   ├── news/          # 新闻模块
│   │   ├── base.py
│   │   ├── eastmoney.py
│   │   ├── aggregator.py
│   │   └── sentiment.py
│   └── adapters/     # 数据适配器
│       └── stock_adapter.py
├── graph/             # 工作流
│   ├── state.py
│   └── trading_graph.py
├── llm_adapters/      # LLM适配器
├── traders/           # 交易执行
│   └── trader.py
├── api/               # API
│   └── analyzer.py
└── examples/          # 示例
    ├── basic_usage.py
    └── batch_analysis.py
```

## License

MIT
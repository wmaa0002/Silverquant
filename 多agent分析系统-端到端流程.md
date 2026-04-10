# 多Agent分析系统端到端完整流程

## 一、系统概览

```
单只股票分析流程：约 8-11 次 LLM调用
                    ↓
        ┌───────────────────────────────┐
        │       1. 数据获取阶段          │
        └───────────────────────────────┘
                    ↓
        ┌───────────────────────────────┐
        │    2. 分析师并行阶段 (3个)      │
        │  Market + News + Fundamentals │
        └───────────────────────────────┘
                    ↓
        ┌───────────────────────────────┐
        │    3. 研究员并行阶段 (2个)      │
        │     Bull + Bear Researchers   │
        └───────────────────────────────┘
                    ↓
        ┌───────────────────────────────┐
        │      4. 三方辩论阶段 (3个)     │
        │  Conservative + Neutral +      │
        │     Aggressive Debaters      │
        └───────────────────────────────┘
                    ↓
        ┌───────────────────────────────┐
        │      5. 决策生成阶段           │
        │  ResearchManager + RiskManager  │
        │        + Trader               │
        └───────────────────────────────┘
                    ↓
        ┌───────────────────────────────┐
        │      6. 结果存储阶段           │
        │  DuckDB + ChromaDB (可选)      │
        └───────────────────────────────┘
```

---

## 二、详细流程

### 阶段1: 数据获取 (调用外部API)

#### 1.1 K线数据获取
```
StockDataAdapter.get_market_data()
├── 数据源: DuckDB本地缓存优先
├── 备用: akshare AKShare数据
└── 返回: DataFrame [date, open, high, low, close, volume, amount]
```

#### 1.2 新闻数据获取
```
NewsAggregator.get_stock_news()
├── 数据源: 东方财富 (eastmoney)
├── 返回: List[NewsItem] (title, content, source, published_at, sentiment)
└── 情感分析: SentimentAnalyzer (基于词典)
```

#### 1.3 基本面数据获取
```
StockDataAdapter.get_fundamentals()
├── 数据源: akshare 财务数据
├── 返回: Dict {
    'valuation': P/E, P/B, P/S,
    'profitability': ROE, 毛利率,
    'growth': 营收增长, 利润增长
}
```

---

### 阶段2: 分析师并行阶段 (3个Agent)

每个分析师都是独立的LLM调用，**并行执行**。

#### 2.1 MarketAnalyst (技术分析师)
```python
LLM调用 #1: MarketAnalyst.run()

输入:
- stock_code: '600519'
- price_data: DataFrame (120天K线)

处理:
- 计算技术指标: MA, MACD, KDJ, RSI, 布林带
- 生成支撑/压力位分析
- 识别K线形态

输出:
- market_report: str (技术分析报告)
```

#### 2.2 NewsAnalyst (新闻分析师)
```python
LLM调用 #2: NewsAnalyst.run()

输入:
- stock_code: '600519'
- news_list: List[NewsItem] (20条新闻)

处理:
- 分析新闻情感 (正面/负面/中性)
- 识别关键事件
- 评估新闻对股价影响

输出:
- news_report: str (新闻分析报告)
```

#### 2.3 FundamentalsAnalyst (基本面分析师)
```python
LLM调用 #3: FundamentalsAnalyst.run()

输入:
- stock_code: '600519'
- fundamentals_data: Dict (估值、盈利、成长数据)

处理:
- 评估估值水平
- 分析盈利能力
- 判断成长性

输出:
- fundamentals_report: str (基本面分析报告)
```

---

### 阶段3: 研究员并行阶段 (2个Agent)

#### 3.1 BullResearcher (做多研究员)
```python
LLM调用 #4: BullResearcher.run()

输入:
- reports: {market, news, fundamentals} 报告
- stock_code: '600519'

处理:
- 从三份报告中提取看多论点
- 生成3-5个看多理由
- 给出目标价和上涨空间

输出:
- bull_research: str
- bull_confidence: float (0.0-1.0)
```

#### 3.2 BearResearcher (做空研究员)
```python
LLM调用 #5: BearResearcher.run()

输入:
- reports: {market, news, fundamentals} 报告
- stock_code: '600519'

处理:
- 从三份报告中提取看空论点
- 生成3-5个看空理由
- 给出风险提示

输出:
- bear_research: str
- bear_confidence: float (0.0-1.0)
```

---

### 阶段4: 三方辩论阶段 (3个Agent)

辩论者**并行执行**，然后聚合结果。

#### 4.1 ConservativeDebator (保守型辩论者)
```python
LLM调用 #6: ConservativeDebator.debate()

立场: 保守
关注: 风险控制、安全边际
输入: bull_research, bear_research
输出: {stance, arguments, risk_points, confidence, recommended_position}
```

#### 4.2 NeutralDebater (中性辩论者)
```python
LLM调用 #7: NeutralDebater.debate()

立场: 中性
关注: 多空平衡、客观分析
输入: bull_research, bear_research
输出: {stance, arguments, risk_points, confidence, recommended_position}
```

#### 4.3 AggressiveDebater (激进型辩论者)
```python
LLM调用 #8: AggressiveDebater.debate()

立场: 激进
关注: 机会把握、进攻性
输入: bull_research, bear_research
输出: {stance, arguments, risk_points, confidence, recommended_position}
```

#### 4.4 DebateAggregator (辩论聚合器)
```
聚合规则:
- 2+ 方同意 HIGH → final_risk=HIGH, position=0%
- 2+ 方同意 LOW → final_risk=LOW, position=30%
- 否则 → final_risk=MEDIUM, position=15%

输出: {
    conservative_view: {...},
    neutral_view: {...},
    aggressive_view: {...},
    final_risk_level: 'MEDIUM',
    recommended_position: 0.15,
    consensus: '辩论共识描述'
}
```

---

### 阶段5: 决策生成阶段 (3个Agent)

#### 5.1 初步决策 (基于研究员结果)
```
决策规则:
- if bull_confidence > bear_confidence + 0.2 → 买入
- if bear_confidence > bull_confidence + 0.2 → 卖出/观望
- else → 观望
```

#### 5.2 ResearchManager (研究经理)
```python
LLM调用 #9: ResearchManager.conduct_research()

输入:
- reports: 分析师报告
- research: {bull_research, bear_research}

输出:
- recommendation: str (最终建议)
- reasoning: str (推理过程)
- key_points: List[str] (关键点)
- confidence: float
```

#### 5.3 RiskManager (风险经理)
```python
LLM调用 #10: RiskManager.assess_risk()

输入:
- investment_decision: '买入'
- confidence: 0.75
- bull_research: str
- bear_research: str
- current_price: float

输出:
- risk_level: 'LOW' | 'MEDIUM' | 'HIGH'
- risk_score: float
- stop_loss: float
- position_size: float
```

#### 5.4 Trader (交易员)
```python
Trader.generate_trading_signal()

输入:
- investment_decision: '买入'
- risk_assessment: {...}
- current_price: 1700.0

输出:
{
    action: 'BUY',           # BUY/SELL/HOLD
    entry_price: 1700.0,    # 入场价
    stop_loss: 1615.0,       # 止损价 (跌5%)
    take_profit: 1955.0,     # 止盈价 (涨15%)
    position_size: 0.3,      # 仓位 30%
    quantity: 100,           # 买入数量
    reasoning: str
}
```

---

### 阶段6: 结果存储阶段

#### 6.1 DuckDB存储 (Structured Results)
```python
ResultAdapter.save_analysis_result()

目标表: agent_analysis_results

字段:
- run_id: UUID
- symbol: '600519'
- trade_date: '2024-05-10'
- result_json: JSON完整结果
- created_at: timestamp

位置: data/Astock3.duckdb
```

#### 6.2 ChromaDB存储 (Vector Memory)
```python
MemoryManager.save_analysis_result()

集合: analysis

存储内容:
- embedding: 分析报告的向量表示
- text: 原始分析报告文本
- metadata: {symbol, trade_date, decision, confidence}

位置: data/agent_memory/ (可选)
```

---

## 三、LLM调用次数汇总

| 阶段 | Agent | LLM调用次数 |
|------|-------|------------|
| **分析师阶段** | MarketAnalyst | 1 |
| | NewsAnalyst | 1 |
| | FundamentalsAnalyst | 1 |
| **研究员阶段** | BullResearcher | 1 |
| | BearResearcher | 1 |
| **辩论阶段** | ConservativeDebater | 1 |
| | NeutralDebater | 1 |
| | AggressiveDebater | 1 |
| **决策阶段** | ResearchManager | 1 |
| | RiskManager | 1 |
| **总计** | **10个Agent** | **10次LLM调用** |

---

## 四、数据流向图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        外部数据源                                    │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ DuckDB  │  │ akshare  │  │ 东方财富  │  │ akshare财务数据  │   │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
└───────┼────────────┼────────────┼────────────────┼──────────────┘
        │            │            │                │
        ▼            ▼            ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     数据获取阶段                                     │
│  ┌────────────────┐  ┌─────────────────┐  ┌────────────────────┐   │
│  │ StockAdapter   │  │ NewsAggregator  │  │ StockAdapter       │   │
│  │ get_market_data│  │ get_stock_news  │  │ get_fundamentals   │   │
│  └───────┬────────┘  └────────┬────────┘  └─────────┬──────────┘   │
│          │                    │                      │              │
│          ▼                    ▼                      ▼              │
│     price_data           news_list             fundamentals_data    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   并行分析师阶段 (ThreadPool)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐     │
│  │MarketAnalyst│  │ NewsAnalyst  │  │ FundamentalsAnalyst  │     │
│  │  LLM调用#1  │  │  LLM调用#2   │  │    LLM调用#3        │     │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘     │
│         │                 │                     │                  │
│         ▼                 ▼                     ▼                  │
│     market_report     news_report        fundamentals_report       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   并行研究员阶段 (ThreadPool)                         │
│  ┌─────────────────┐         ┌─────────────────┐                   │
│  │  BullResearcher │         │ BearResearcher  │                   │
│  │   LLM调用#4     │         │   LLM调用#5     │                   │
│  └────────┬────────┘         └────────┬────────┘                   │
│           │                            │                             │
│           ▼                            ▼                             │
│    bull_research               bear_research                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   三方辩论阶段 (并行→聚合)                            │
│  ┌────────────────┐ ┌────────────┐ ┌────────────────┐               │
│  │ Conservative  │ │  Neutral   │ │  Aggressive   │               │
│  │  LLM调用#6     │ │ LLM调用#7  │ │  LLM调用#8     │               │
│  └───────┬────────┘ └─────┬──────┘ └───────┬────────┘               │
│          │                │                │                        │
│          └────────────────┴────────────────┘                        │
│                           │                                         │
│                           ▼                                         │
│                   DebateAggregator                                  │
│                   (投票聚合)                                        │
│                           │                                         │
│                           ▼                                         │
│                   debate_result                                     │
│                   {final_risk_level, recommended_position}         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      决策生成阶段                                    │
│  ┌────────────────────┐  ┌─────────────────┐  ┌──────────────┐      │
│  │   ResearchManager │  │   RiskManager   │  │    Trader    │      │
│  │    LLM调用#9       │  │   LLM调用#10    │  │  (规则计算)  │      │
│  └─────────┬─────────┘  └────────┬────────┘  └──────┬───────┘      │
│            │                       │                  │              │
│            ▼                       ▼                  ▼              │
│    research_result         risk_result        trading_signal       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        结果存储阶段                                  │
│  ┌─────────────────────┐        ┌─────────────────────────┐           │
│  │   ResultAdapter     │        │   MemoryManager        │           │
│  │  (DuckDB存储)       │        │  (ChromaDB存储)       │           │
│  │ agent_analysis_results│     │  分析报告向量           │           │
│  └─────────────────────┘        └─────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 五、返回结果结构

```python
{
    'success': True,
    'run_id': '600519_20240510_abc123',  # 唯一标识
    
    # 核心决策
    'final_decision': '买入',      # 买入/观望/卖出
    'confidence': 0.75,             # 置信度 0.0-1.0
    'reasoning': '做多置信度=0.80, 做空置信度=0.50',
    
    # 分析师报告
    'reports': {
        'market': '技术面分析...',        # 约200-500字
        'news': '新闻分析...',           # 约200-500字
        'fundamentals': '基本面分析...'   # 约200-500字
    },
    
    # 研究员结论
    'bull_research': '做多论点...',
    'bear_research': '做空论点...',
    'bull_confidence': 0.80,
    'bear_confidence': 0.50,
    
    # 辩论结果
    'debate_round': {
        'conservative_view': {
            'stance': '保守',
            'arguments': ['论点1', '论点2'],
            'risk_points': ['风险1', '风险2'],
            'confidence': 0.6,
            'recommended_position': 0.1
        },
        'neutral_view': {
            'stance': '中性',
            'arguments': [...],
            'confidence': 0.65,
            'recommended_position': 0.2
        },
        'aggressive_view': {
            'stance': '激进',
            'arguments': [...],
            'confidence': 0.7,
            'recommended_position': 0.3
        },
        'final_risk_level': 'MEDIUM',   # LOW/MEDIUM/HIGH
        'recommended_position': 0.15,    # 15%仓位
        'consensus': '三方辩论完成，置信度0.65'
    },
    
    # 研究经理结论
    'research': {
        'recommendation': '买入',
        'reasoning': '综合分析...',
        'key_points': ['要点1', '要点2'],
        'confidence': 0.75
    },
    
    # 风险评估
    'risk': {
        'risk_level': 'MEDIUM',
        'risk_score': 0.45,
        'stop_loss': 1615.0,
        'position_size': 0.15
    },
    
    # 交易信号
    'trading_signal': {
        'action': 'BUY',           # BUY/SELL/HOLD
        'entry_price': 1700.0,      # 入场价
        'stop_loss': 1615.0,        # 止损价 (entry*0.95)
        'take_profit': 1955.0,      # 止盈价 (entry*1.15)
        'position_size': 0.15,      # 15%仓位
        'quantity': 88,            # 买入数量 (100000*0.15/1700≈88)
        'reasoning': '基于买入决策...'
    },
    
    # 历史记忆上下文
    'memory_context': [
        {'text': '上次分析...', 'date': '2024-05-01', 'decision': '观望'},
        {'text': '历史分析...', 'date': '2024-04-15', 'decision': '买入'}
    ],
    
    # 元信息
    'symbol': '600519',
    'trade_date': '2024-05-10'
}
```

---

## 六、数据存储位置

### 6.1 DuckDB (结构化数据)

**路径**: `data/Astock3.duckdb`

**表**: `agent_analysis_results`

```sql
CREATE TABLE agent_analysis_results (
    run_id VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    trade_date DATE,
    result_json JSON,
    created_at TIMESTAMP
);
```

### 6.2 ChromaDB (向量数据，可选)

**路径**: `data/agent_memory/`

**集合**: `analysis`

**字段**:
- id: run_id
- embedding: 向量 (1536维)
- text: 分析报告文本
- metadata: {symbol, trade_date, decision, confidence}

### 6.3 CSV导出 (测试结果)

**路径**: `agent_integration/test_results/`

**文件**: `YYYY-MM-DD_test_results.csv`

---

## 七、执行时间估算

| 阶段 | 预计耗时 |
|------|----------|
| 数据获取 | 1-3秒 |
| 分析师并行 (3个) | 5-15秒 |
| 研究员并行 (2个) | 3-10秒 |
| 三方辩论并行 (3个) | 5-15秒 |
| 决策生成 (2个LLM) | 3-8秒 |
| 结果存储 | 0.5-1秒 |
| **总计** | **18-52秒** |

**平均**: 约30秒/只股票

---

## 八、API调用链路图

```
analyze_stock('600519', '2024-05-10')
│
├─ get_llm_adapter()
│  └─ create_llm_by_provider('deepseek', 'deepseek-chat')
│     └─ ChatDeepSeek(api_key=...)
│
├─ StockDataAdapter().get_market_data()
│  ├─ DuckDB.query('SELECT ... FROM daily_price WHERE code="600519"')
│  └─ akshare.stock_zh_a_hist() [fallback]
│
├─ NewsAggregator().get_stock_news()
│  └─ EastMoneyNews().get_stock_news()
│     └─ akshare.news_cn_stock() [或直接调用东方财富API]
│
├─ StockDataAdapter().get_fundamentals()
│  └─ akshare.stock_financial_analysis_indicator()
│
├─ TradingAgentsGraph().propagate()
│  │
│  ├─ [并行] MarketAnalyst.run()
│  │  └─ llm.chat([{'role': 'system', ...}, {'role': 'user', ...}])
│  │     └─ LLM调用 #1
│  │
│  ├─ [并行] NewsAnalyst.run()
│  │  └─ llm.chat([...])
│  │     └─ LLM调用 #2
│  │
│  ├─ [并行] FundamentalsAnalyst.run()
│  │  └─ llm.chat([...])
│  │     └─ LLM调用 #3
│  │
│  ├─ [并行] BullResearcher.run()
│  │  └─ llm.chat([...])
│  │     └─ LLM调用 #4
│  │
│  ├─ [并行] BearResearcher.run()
│  │  └─ llm.chat([...])
│  │     └─ LLM调用 #5
│  │
│  ├─ [并行] ConservativeDebater.debate()
│  │  └─ llm.chat([...])
│  │     └─ LLM调用 #6
│  │
│  ├─ [并行] NeutralDebater.debate()
│  │  └─ llm.chat([...])
│  │     └─ LLM调用 #7
│  │
│  ├─ [并行] AggressiveDebater.debate()
│  │  └─ llm.chat([...])
│  │     └─ LLM调用 #8
│  │
│  ├─ ResearchManager.conduct_research()
│  │  └─ llm.chat([...])
│  │     └─ LLM调用 #9
│  │
│  └─ RiskManager.assess_risk()
│     └─ llm.chat([...])
│        └─ LLM调用 #10
│
├─ Trader.generate_trading_signal() [规则计算，无LLM]
│
├─ ResultAdapter.save_analysis_result()
│  └─ DuckDB INSERT INTO agent_analysis_results
│
└─ MemoryManager.save_analysis_result() [可选]
   └─ ChromaDB.add(embedding, text, metadata)

返回完整分析结果
```

---

## 九、总结

### 参与Agent数量: 10个

| 角色 | Agent | 数量 |
|------|-------|------|
| 分析师 | MarketAnalyst, NewsAnalyst, FundamentalsAnalyst | 3 |
| 研究员 | BullResearcher, BearResearcher | 2 |
| 辩论者 | ConservativeDebater, NeutralDebater, AggressiveDebater | 3 |
| 经理 | ResearchManager, RiskManager | 2 |
| **总计** | | **10** |

### LLM调用次数: 10次

### 外部API调用

| API | 调用次数 | 说明 |
|-----|----------|------|
| DeepSeek API | 10 | LLM调用 |
| DuckDB | 1-2 | K线数据查询 |
| akshare | 2-3 | 新闻、财务数据 |

### 存储位置

| 存储 | 位置 | 内容 |
|------|------|------|
| DuckDB | `data/Astock3.duckdb` | 结构化分析结果 |
| ChromaDB | `data/agent_memory/` | 向量记忆 (可选) |
| CSV | `agent_integration/test_results/` | 测试结果导出 |

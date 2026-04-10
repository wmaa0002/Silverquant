# TradingAgents-CN 集成完成计划

> **生成时间**: 2026-03-30
> **版本**: 1.0
> **基于**: `.sisyphus/plans/tradingagent-cn-integration-TODO.md`
> **目的**: 完成剩余验收标准

---

## TL;DR

> **核心问题**: 核心代码已实现，但存在4个关键缺口导致验收标准无法通过
> 
> **缺口数量**: 4个关键问题
> - 1个CRITICAL (阻断): Flask API路由未连接
> - 1个CRITICAL (阻断): DatabaseManager schema bug导致结果无法存储
> - 2个HIGH: LLM适配器导出缺失 + LLM情感分析未实现

---

## 验证结果摘要

### ✅ 已验证通过 (代码存在且正常工作)

| 模块 | 状态 | 说明 |
|------|------|------|
| T2-T6 | ✅ | LLM适配器核心实现正常 |
| T7-T9 | ✅ | 新闻/数据流核心实现正常 |
| T11 | ✅ | StockDataAdapter可获取数据 |
| T12-T21 | ✅ | 所有Agent类实现正常 |
| T22 | ✅ | Trader类实现正常 |
| T23 | ✅ | DebateAggregator实现正常 |
| T25 | ✅ | ConfigAdapter实现正常 |

### ❌ 存在问题 (需要修复)

| 任务 | 问题 | 严重度 | 位置 |
|------|------|--------|------|
| T28 | Flask API路由未连接 | CRITICAL | dashboard/app.py |
| T27 | DatabaseManager schema bug | CRITICAL | database/schema.py:511 |
| T3 | __init__.py缺少导出 | HIGH | llm_adapters/__init__.py:15-17 |
| T10 | LLM情感分析未实现 | HIGH | sentiment.py:31-34 |

---

## 工作目标

### 必须完成 (Must Have)

1. **T28: Flask API路由** - ✅ 已完成
2. **T27: ResultAdapter存储** - ✅ 已完成
3. **T3: LLM导出** - ✅ 已完成
4. **T10: LLM情感** - ✅ 已完成

### 可选完成 (Nice to Have)

5. T11数据格式验证 - ✅ 已完成（已验证可获取数据）

---

## 执行策略

### 并行工作流 (5个Wave)

```
Wave 1 (Foundation - 无依赖):
├── T-FIX-1: 修复DatabaseManager schema (database/schema.py)
├── T-FIX-2: 添加LLM适配器导出 (llm_adapters/__init__.py)
└── T-FIX-3: 实现LLM情感分析 (sentiment.py)

Wave 2 (API - 依赖Wave1的Database修复):
├── T-IMPLEMENT-1: 创建Flask API路由 (dashboard/agent_api.py)

Wave 3 (验证):
├── T-VERIFY-1: 运行完整导入测试
├── T-VERIFY-2: 运行API端到端测试
└── T-VERIFY-3: 验证结果存储到DuckDB

Wave FINAL:
└── T-FINAL: 更新TODO文件标记验收标准为完成
```

---

## TODOs

---

### T-FIX-1: 修复DatabaseManager schema bug

**问题**: `CREATE TABLE portfolio_daily` 导致 `CatalogException: Table with name "portfolio_daily" already exists`

**文件**: `database/schema.py` (约第511行)

**当前代码**:
```python
CREATE TABLE portfolio_daily (
    ...
)
```

**修复为**:
```python
CREATE TABLE IF NOT EXISTS portfolio_daily (
    ...
)
```

**影响**: 修复后 ResultAdapter._ensure_table() 才能正常工作

**推荐Agent**: `quick`

**并行性**: YES - 可立即执行

**验收标准**:
- [ ] `python -c "from database.db_manager import DatabaseManager; dm = DatabaseManager(); print('OK')"` 不报错

**QA场景**:
```
Scenario: DatabaseManager初始化不再报portfolio_daily错误
  Tool: Bash
  Preconditions: database/schema.py已修复
  Steps:
    1. python -c "from database.db_manager import DatabaseManager; dm = DatabaseManager(); print('DatabaseManager initialized OK')"
  Expected Result: 输出"DatabaseManager initialized OK"，无异常
  Failure Indicators: CatalogException about portfolio_daily
  Evidence: .sisyphus/evidence/t-fix-1-db-init.log
```

---

### T-FIX-2: 添加LLM适配器导出

**问题**: `__init__.py`只导出TokenTracker和OpenAICompatibleBase，缺少工厂函数

**文件**: `agent_integration/llm_adapters/__init__.py`

**当前代码** (第15-17行):
```python
from agent_integration.llm_adapters.base import TokenTracker, OpenAICompatibleBase
```

**修复为**:
```python
from agent_integration.llm_adapters.base import TokenTracker, OpenAICompatibleBase, get_global_token_tracker, reset_global_token_tracker
from agent_integration.llm_adapters.factory import create_llm_by_provider, create_llm_by_model
from agent_integration.llm_adapters.deepseek import ChatDeepSeek
from agent_integration.llm_adapters.minimax import ChatMiniMax
```

**推荐Agent**: `quick`

**并行性**: YES - 可立即执行

**验收标准**:
- [ ] `from agent_integration.llm_adapters import create_llm_by_provider` 不报错

**QA场景**:
```
Scenario: LLM工厂函数可正常导入
  Tool: Bash
  Preconditions: __init__.py已修复
  Steps:
    1. python -c "from agent_integration.llm_adapters import create_llm_by_provider, create_llm_by_model, ChatDeepSeek, ChatMiniMax; print('All imports OK')"
  Expected Result: 输出"All imports OK"
  Failure Indicators: ImportError
  Evidence: .sisyphus/evidence/t-fix-2-imports.log
```

---

### T-FIX-3: 实现LLM情感分析

**问题**: `SentimentAnalyzer(use_llm=True)` 参数存在但未使用

**文件**: `agent_integration/dataflows/news/sentiment.py`

**当前代码** (第31-34行):
```python
def __init__(self):
    """初始化情感分析器"""
    self.positive_set = set(self.POSITIVE_WORDS)
    self.negative_set = set(self.NEGATIVE_WORDS)
```

**需要添加**:
```python
def __init__(self, use_llm=False, llm_adapter=None):
    """初始化情感分析器
    
    Args:
        use_llm: 是否使用LLM进行情感分析
        llm_adapter: LLM适配器实例
    """
    self.use_llm = use_llm
    self.llm_adapter = llm_adapter
    self.positive_set = set(self.POSITIVE_WORDS)
    self.negative_set = set(self.NEGATIVE_WORDS)
```

**并修改analyze_text方法**:
```python
def analyze_text(self, text: str) -> Tuple[Sentiment, float]:
    """直接分析文本情感
    
    Args:
        text: 文本内容
        
    Returns:
        (Sentiment, score) - score范围 [-1.0, 1.0]
    """
    # 如果启用LLM且有适配器，使用LLM分析
    if self.use_llm and self.llm_adapter:
        return self._analyze_with_llm(text)
    
    score = self._calculate_score(text)
    
    if score > 0.1:
        return Sentiment.POSITIVE, score
    elif score < -0.1:
        return Sentiment.NEGATIVE, score
    else:
        return Sentiment.NEUTRAL, score

def _analyze_with_llm(self, text: str) -> Tuple[Sentiment, float]:
    """使用LLM进行情感分析"""
    if self.llm_adapter is None:
        return self._calculate_score(text)
    
    prompt = f"""分析以下文本的情感倾向，返回JSON格式：
{{"sentiment": "positive"或"negative"或"neutral", "score": -1.0到1.0之间的分数}}
文本：{text[:500]}"""
    
    response = self.llm_adapter.chat([
        {'role': 'user', 'content': prompt}
    ])
    
    # 解析JSON响应
    try:
        import json
        result = json.loads(response)
        sentiment_str = result.get('sentiment', 'neutral')
        score = float(result.get('score', 0.0))
        
        sentiment_map = {
            'positive': Sentiment.POSITIVE,
            'negative': Sentiment.NEGATIVE,
            'neutral': Sentiment.NEUTRAL
        }
        return sentiment_map.get(sentiment_str, Sentiment.NEUTRAL), score
    except:
        return Sentiment.NEUTRAL, 0.0
```

**推荐Agent**: `quick`

**并行性**: YES - 可立即执行

**验收标准**:
- [ ] `SentimentAnalyzer(use_llm=True, llm_adapter=llm)` 可正常实例化
- [ ] 当use_llm=True时，使用LLM分析

**QA场景**:
```
Scenario: 词典情感分析正常工作
  Tool: Bash
  Preconditions: sentiment.py已修复
  Steps:
    1. python -c "
from agent_integration.dataflows.news.sentiment import SentimentAnalyzer
analyzer = SentimentAnalyzer()
sentiment, score = analyzer.analyze_text('茅台股价上涨')
print(f'sentiment={sentiment.value}, score={score}')
assert sentiment.value == 'positive' and score > 0
"
  Expected Result: sentiment=positive, score>0
  Evidence: .sisyphus/evidence/t-fix-3-dict.log

Scenario: LLM情感分析可启用
  Tool: Bash
  Preconditions: sentiment.py已修复, 有mock LLM
  Steps:
    1. python -c "
from agent_integration.dataflows.news.sentiment import SentimentAnalyzer
class MockLLM:
    def chat(self, messages):
        return '{\"sentiment\": \"positive\", \"score\": 0.8}'
analyzer = SentimentAnalyzer(use_llm=True, llm_adapter=MockLLM())
sentiment, score = analyzer.analyze_text('测试文本')
print(f'LLM: sentiment={sentiment.value}, score={score}')
"
  Expected Result: LLM: sentiment=positive, score=0.8
  Evidence: .sisyphus/evidence/t-fix-3-llm.log
```

---

### T-IMPLEMENT-1: 创建Flask API路由

**问题**: TODO要求`POST /api/agent/analyze`可用，但dashboard/app.py中无此路由

**文件**: `dashboard/agent_api.py` (新建)

**实现内容**:
```python
"""
Flask API - Agent分析接口
"""
import sys
import os
from flask import Blueprint, request, jsonify
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_integration.api.analyzer import analyze_stock, health_check, get_analysis_history

agent_bp = Blueprint('agent', __name__, url_prefix='/api/agent')

@agent_bp.route('/analyze', methods=['POST'])
def analyze():
    """分析股票
    
    POST /api/agent/analyze
    Body: {"symbol": "600519", "trade_date": "2024-05-10"}
    
    Returns: JSON格式分析结果
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400
    
    symbol = data.get('symbol')
    trade_date = data.get('trade_date')
    
    if not symbol:
        return jsonify({'success': False, 'error': '缺少symbol参数'}), 400
    
    if not trade_date:
        trade_date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        result = analyze_stock(symbol, trade_date)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@agent_bp.route('/history', methods=['GET'])
def history():
    """获取分析历史
    
    GET /api/agent/history?symbol=600519&limit=10
    
    Returns: JSON格式历史记录列表
    """
    symbol = request.args.get('symbol')
    limit = int(request.args.get('limit', 10))
    
    try:
        results = get_analysis_history(symbol=symbol, limit=limit)
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@agent_bp.route('/health', methods=['GET'])
def health():
    """健康检查
    
    GET /api/agent/health
    
    Returns: JSON格式健康状态
    """
    try:
        status = health_check()
        return jsonify(status)
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500
```

**并修改dashboard/app.py**添加:
```python
# 在文件开头添加导入
from dashboard.agent_api import agent_bp

# 在create_app()函数中注册蓝图
app.register_blueprint(agent_bp)
```

**推荐Agent**: `quick`

**并行性**: NO - 依赖T-FIX-1完成(DatabaseManager需要正常工作)

**验收标准**:
- [ ] `POST /api/agent/analyze` 返回JSON格式结果
- [ ] `GET /api/agent/history` 返回历史记录
- [ ] `GET /api/agent/health` 返回健康状态

**QA场景**:
```
Scenario: API路由正常响应
  Tool: Bash (需要先启动Flask)
  Preconditions: dashboard/agent_api.py已创建, dashboard/app.py已修改
  Steps:
    1. cd /Users/mawenhao/Desktop/code/股票策略 && python -c "from dashboard.app import create_app; app = create_app(); client = app.test_client()"
    2. client.post('/api/agent/analyze', json={'symbol': '600519', 'trade_date': '2024-05-10'})
  Expected Result: 返回JSON包含success, run_id, final_decision等字段
  Failure Indicators: 404 Not Found 或 500 Internal Server Error
  Evidence: .sisyphus/evidence/t-impl-1-api-test.log

Scenario: Health端点正常
  Tool: Bash
  Preconditions: 同上
  Steps:
    1. client.get('/api/agent/health')
  Expected Result: 返回JSON包含status: 'healthy'或'degraded'
  Evidence: .sisyphus/evidence/t-impl-1-health-test.log
```

---

## 最终验证Wave

> 4个验证并行执行，全部通过后更新TODO文件

- [ ] **F1: 导入验证** — 所有模块可正常导入
  - `python -c "from agent_integration.llm_adapters import create_llm_by_provider; from agent_integration.dataflows.news.sentiment import SentimentAnalyzer; from agent_integration.api.analyzer import analyze_stock; print('All imports OK')"`

- [ ] **F2: 数据库验证** — ResultAdapter可存储和读取
  - 运行端到端分析，验证结果存入DuckDB

- [ ] **F3: API验证** — Flask路由正常响应
  - curl测试所有3个端点

- [ ] **F4: TODO更新** — 标记所有验收标准为完成

---

## 成功标准

```bash
# 1. 导入测试
python -c "from agent_integration.llm_adapters import create_llm_by_provider, create_llm_by_model; print('LLM imports OK')"
python -c "from agent_integration.dataflows.news.sentiment import SentimentAnalyzer; print('SentimentAnalyzer OK')"
python -c "from agent_integration.api.analyzer import analyze_stock; print('API OK')"

# 2. Flask启动测试
curl -X POST http://localhost:5001/api/agent/analyze -H "Content-Type: application/json" -d '{"symbol": "600519"}' | python -m json.tool

# 3. 数据库验证
python -c "
from agent_integration.adapters.result_adapter import ResultAdapter
ra = ResultAdapter()
# 应该不报错
print('ResultAdapter OK')
"
```

---

## 预计工作量

| 任务 | 估计时间 | 类型 |
|------|----------|------|
| T-FIX-1 | 5分钟 | quick |
| T-FIX-2 | 2分钟 | quick |
| T-FIX-3 | 15分钟 | quick |
| T-IMPLEMENT-1 | 20分钟 | quick |
| F1-F4验证 | 15分钟 | unspecified-high |
| **总计** | **~1小时** | |

---

## 下一步

1. 运行 `/start-work tradingagent-cn-completion`
2. 执行 T-FIX-1 到 T-IMPLEMENT-1
3. 运行最终验证
4. 更新原始TODO文件标记验收标准完成

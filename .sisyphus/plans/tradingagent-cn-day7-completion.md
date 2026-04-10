# TradingAgents-CN Day 7 完成计划

> **生成时间**: 2026-03-30
> **版本**: 1.0
> **基于**: `.sisyphus/plans/tradingagent-cn-integration-TODO.md`
> **目的**: 完成 Day 7 剩余优化和文档任务

---

## TL;DR

> **剩余任务**: 4项
> - T30: Token追踪优化 (添加报表和成本预警)
> - T31: 缓存优化 (Redis, 可选)
> - T32: 异常处理完善
> - T34: 示例代码 (缺少 flask_integration.py)

---

## 当前状态

| 任务 | 状态 | 说明 |
|------|------|------|
| T30 | ⬜ | 需要添加Token使用报表和成本预警 |
| T31 | ⬜ | Redis缓存 (可选) |
| T32 | ⬜ | API超时、LLM降级、网络重试 |
| T33 | ✅ | README.md 已完整 |
| T34 | ⬜ | 缺少 flask_integration.py |

---

## 执行策略

```
Wave 1 (文档 - 无依赖):
├── T-CREATE-1: 创建 flask_integration.py 示例

Wave 2 (优化):
├── T-IMPROVE-1: 添加Token使用报表和成本预警
├── T-IMPROVE-2: 添加异常处理完善

Wave 3 (可选):
└── T-OPTIONAL-1: Redis缓存 (T31)

Wave FINAL:
└── 更新验收检查清单
```

---

## TODOs

---

### T-CREATE-1: 创建 flask_integration.py 示例

**文件**: `agent_integration/examples/flask_integration.py` (新建)

**实现内容**:
```python
"""
Flask API集成示例 - flask_integration.py

展示如何在Flask应用中集成agent_integration模块。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from dashboard.agent_api import agent_bp


def create_app():
    """创建Flask应用并注册蓝图"""
    from dashboard.app import app as base_app
    
    # 注册Agent API蓝图
    base_app.register_blueprint(agent_bp)
    
    return base_app


@app.route('/custom-route')
def custom_route():
    """自定义路由示例"""
    return jsonify({'message': 'Hello from custom route!'})


def main():
    """启动Flask开发服务器"""
    app = create_app()
    print("Flask应用已创建，Agent API蓝图已注册")
    print("可访问以下端点:")
    print("  POST /api/agent/analyze - 分析股票")
    print("  GET  /api/agent/history - 获取历史")
    print("  GET  /api/agent/health - 健康检查")
    app.run(host='0.0.0.0', port=5001, debug=True)


if __name__ == '__main__':
    main()
```

**推荐Agent**: `quick`

**并行性**: YES - 可立即执行

**验收标准**:
- [ ] `flask_integration.py` 可独立运行

**QA场景**:
```
Scenario: Flask集成示例可导入
  Tool: Bash
  Preconditions: flask_integration.py已创建
  Steps:
    1. python -c "from agent_integration.examples.flask_integration import create_app; print('Flask integration OK')"
  Expected Result: 输出"Flask integration OK"
  Evidence: .sisyphus/evidence/t-create-1-flask-import.log
```

---

### T-IMPROVE-1: Token使用报表和成本预警

**文件**: `agent_integration/llm_adapters/base.py`

**当前状态**: TokenTracker已存在get_stats()方法

**需要添加**:

1. **每日/每周Token使用报表方法**:
```python
def get_daily_report(self) -> Dict[str, Any]:
    """获取每日Token使用报表"""
    today = datetime.now().date()
    daily_tokens = {
        k: v for k, v in self.usage_records.items()
        if v.get('date', today) == today
    }
    
    total_input = sum(r.get('input_tokens', 0) for r in daily_tokens.values())
    total_output = sum(r.get('output_tokens', 0) for r in daily_tokens.values())
    total_cost = self.calculate_total_cost()
    
    return {
        'date': str(today),
        'input_tokens': total_input,
        'output_tokens': total_output,
        'total_tokens': total_input + total_output,
        'total_cost': total_cost,
        'request_count': len(daily_tokens)
    }

def get_weekly_report(self) -> Dict[str, Any]:
    """获取每周Token使用报表"""
    week_ago = datetime.now().date() - timedelta(days=7)
    # ... 类似实现
```

2. **成本预警方法**:
```python
def check_cost_alert(self, threshold: float = 10.0) -> Optional[Dict]:
    """检查是否超过成本阈值
    
    Args:
        threshold: 阈值（默认10元）
        
    Returns:
        预警信息，如果未超阈值则返回None
    """
    total_cost = self.calculate_total_cost()
    
    if total_cost >= threshold:
        return {
            'alert': True,
            'threshold': threshold,
            'current_cost': total_cost,
            'percentage': (total_cost / threshold) * 100
        }
    return None
```

**推荐Agent**: `quick`

**并行性**: YES - 可立即执行

**验收标准**:
- [ ] TokenTracker有get_daily_report()方法
- [ ] TokenTracker有check_cost_alert()方法

**QA场景**:
```
Scenario: Token报表功能正常
  Tool: Bash
  Preconditions: base.py已添加报表方法
  Steps:
    1. python -c "
from agent_integration.llm_adapters.base import TokenTracker
tt = TokenTracker()
report = tt.get_daily_report()
print(f'Daily report: {report}')
alert = tt.check_cost_alert(threshold=1.0)
print(f'Alert: {alert}')
"
  Expected Result: 输出报表和预警信息
  Evidence: .sisyphus/evidence/t-improve-1-token-report.log
```

---

### T-IMPROVE-2: 异常处理完善

**文件**: `agent_integration/api/analyzer.py`

**需要添加**:

1. **API超时处理**:
```python
# 在analyze_stock函数中添加超时
import signal

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("API调用超时")

def analyze_stock_with_timeout(symbol, trade_date, timeout=120):
    """带超时控制的股票分析"""
    # 注册超时处理器
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)  # 120秒超时
    
    try:
        result = analyze_stock(symbol, trade_date)
        signal.alarm(0)  # 取消超时
        return result
    except TimeoutError as e:
        return {
            'success': False,
            'symbol': symbol,
            'trade_date': trade_date,
            'error': f'分析超时（超过{timeout}秒）',
            'timeout': True
        }
    except Exception as e:
        signal.alarm(0)
        return {
            'success': False,
            'symbol': symbol,
            'trade_date': trade_date,
            'error': str(e)
        }
```

2. **LLM降级处理**:
```python
def create_llm_with_fallback():
    """创建带降级的LLM适配器"""
    try:
        # 优先使用配置的LLM
        from agent_integration.llm_adapters.factory import create_llm_by_provider
        from agent_integration.adapters.config_adapter import ConfigAdapter
        
        config = ConfigAdapter()
        llm_config = config.get_llm_config()
        
        llm = create_llm_by_provider(
            provider=llm_config.get('provider', 'deepseek'),
            model=llm_config.get('model', 'deepseek-chat'),
            api_key=llm_config.get('api_key'),
        )
        return llm
    except Exception as e:
        print(f"主LLM创建失败: {e}")
        # 降级到简单响应
        return create_fallback_llm()

def create_fallback_llm():
    """创建降级LLM（返回固定响应）"""
    class FallbackLLM:
        def chat(self, messages):
            return "由于服务暂时不可用，无法完成分析。请稍后再试。"
        
        def get_token_usage(self):
            return {'input_tokens': 0, 'output_tokens': 0}
    
    return FallbackLLM()
```

3. **网络错误重试**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm_with_retry(llm, messages):
    """带重试的LLM调用"""
    return llm.chat(messages)
```

**推荐Agent**: `quick`

**并行性**: YES - 可立即执行

**验收标准**:
- [ ] analyze_stock有超时处理
- [ ] LLM有降级处理
- [ ] API返回有意义的错误信息

**QA场景**:
```
Scenario: 异常处理正常工作
  Tool: Bash
  Preconditions: analyzer.py已添加异常处理
  Steps:
    1. python -c "
from agent_integration.api.analyzer import analyze_stock
# 测试错误情况
result = analyze_stock('', '2024-05-10')  # 空symbol
print(f'Error handling: success={result.get(\"success\")}, error={result.get(\"error\", \"none\")}')"
  Expected Result: 返回有意义的错误信息
  Evidence: .sisyphus/evidence/t-improve-2-error-handling.log
```

---

### T-OPTIONAL-1: Redis缓存 (T31)

**文件**: `agent_integration/cache/redis_cache.py` (新建)

**说明**: 此任务为可选任务，需要Redis服务器。如果Redis不可用，应优雅降级。

**实现内容**:
```python
"""
Redis缓存模块 - redis_cache.py

提供分析结果的Redis缓存。
"""
import json
from typing import Optional, Any
import redis

class RedisCache:
    """Redis缓存"""
    
    def __init__(self, host='localhost', port=6379, db=0, ttl=3600):
        self.ttl = ttl
        try:
            self.client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            self.client.ping()  # 测试连接
            self.available = True
        except redis.ConnectionError:
            self.client = None
            self.available = False
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self.available:
            return None
        
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
        except Exception:
            pass
        return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """设置缓存"""
        if not self.available:
            return False
        
        try:
            self.client.setex(
                key,
                ttl or self.ttl,
                json.dumps(value)
            )
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self.available:
            return False
        
        try:
            self.client.delete(key)
            return True
        except Exception:
            return False
```

**推荐Agent**: `quick`

**并行性**: YES - 可立即执行

**验收标准**:
- [ ] RedisCache在Redis不可用时优雅降级
- [ ] 相同请求在TTL内返回缓存

---

## 最终验证

- [x] **V1**: flask_integration.py可导入 ✅
- [x] **V2**: Token报表方法可用 ✅
- [x] **V3**: 异常处理正常工作 ✅
- [x] **V4**: 更新验收检查清单 ✅

---

## 预计工作量

| 任务 | 估计时间 | 类型 |
|------|----------|------|
| T-CREATE-1 | 10分钟 | quick |
| T-IMPROVE-1 | 15分钟 | quick |
| T-IMPROVE-2 | 20分钟 | quick |
| T-OPTIONAL-1 | 15分钟 | quick |
| 验证 | 10分钟 | unspecified-high |
| **总计** | **~70分钟** | |

---

## 下一步

1. 执行 `/start-work day7-completion`
2. 完成所有TODO
3. 更新验收检查清单

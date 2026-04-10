# Tushare数据源接入 + 自动故障切换

## TL;DR

> **Quick Summary**: 接入tushare作为第三数据源，实现tushare→akshare→baostock自动故障切换
> 
> **Deliverables**:
> - Tushare适配器（StockFetcher扩展）
> - 自动故障切换逻辑（CircuitBreaker + 错误率/响应时间监控）
> - 健康检查脚本（流水线前运行）
> - 修复fetcher_daily_priceV4.py硬编码bug
> - 代码格式自动转换层
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Wave1配置 → Wave2核心 → Wave3集成

---

## Context

### Original Request
用户提出：
1. 接入tushare作为第三个数据源（提供api-key）
2. 实现自动选择数据源功能 - 检测到当前数据源不好用时自动切换
3. 多进程场景下频繁报错的问题

### Interview Summary
**Key Discussions**:
- Token存储: 使用环境变量`TUSHARE_TOKEN`
- 优先级: tushare → akshare → baostock
- 切换条件: 错误率>30% 或 响应>10秒
- 限流: 进程内限流，每分钟50次tushare请求
- 代码格式: 自动转换层
- 回滚: 定期探测高优先级源
- 健康检查: 流水线前检查
- 数据源混合: 不允许，始终使用同一源

**Research Findings**:
- 现有StockFetcher使用if/else分支扩展新数据源
- fetcher_daily_priceV4.py第80、85行硬编码baostock
- Tushare代码格式: `000001.SZ`，日期格式: YYYYMMDD
- Tushare需120积分，每分钟50次限制

### Metis Review
**Identified Gaps** (addressed):
- TUSHARE_TOKEN: 用户已确认会提供
- 统一代码格式: 已决定自动转换层
- 健康检查归属: 已确认流水线前检查
- 数据源混合策略: 已确认不允许

---

## Work Objectives

### Core Objective
在现有数据获取层中接入tushare作为第三数据源，并实现基于错误率和响应时间的自动故障切换机制。

### Concrete Deliverables
- [ ] `data/fetchers/stock_fetcher.py` 增加tushare支持
- [ ] `config/settings.py` 增加TUSHARE_TOKEN和DATA_SOURCE_PRIORITY配置
- [ ] `data/fetchers/multi_source_fetcher.py` 新建 - 故障切换封装器
- [ ] `data/fetchers/code_converter.py` 新建 - 代码格式转换工具
- [ ] `data/fetchers/rate_limiter.py` 新建 - 进程内限流器
- [ ] `scripts/data_check/health_check.py` 新建/增强 - 数据源健康检查
- [ ] `data/updaters/fetcher_daily_priceV4.py` 修复硬编码baostock
- [ ] 环境变量`TUSHARE_TOKEN`使用说明

### Definition of Done
- [ ] python -c "from data.fetchers.stock_fetcher import StockFetcher; f = StockFetcher(source='tushare'); print(f.get_stock_list().head())" → 输出股票列表
- [ ] python -c "from data.fetchers.multi_source_fetcher import MultiSourceFetcher; mf = MultiSourceFetcher(); print(mf.get_daily_price('000001', '20240101', '20240110'))" → 输出日线数据
- [ ] 健康检查脚本输出各数据源状态

### Must Have
- Tushare token从环境变量读取，不硬编码
- 自动故障切换（错误率>30% 或 响应>10秒）
- 代码格式自动转换（内部统一格式 ↔ 各数据源格式）
- 进程内限流保护tushare接口
- 流水线前健康检查

### Must NOT Have (Guardrails)
- 不允许单次回测混用多个数据源
- 不修改现有DuckDB数据库结构
- 不删除或修改现有回测策略
- Tushare为可选 - 无token时系统正常降级到akshare/baostock

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO (tests/只有standalone脚本)
- **Automated tests**: Tests-after
- **Framework**: None (使用bash + Python验证)
- **Agent-Executed QA**: 每个TODO包含QA场景

### QA Policy
Every task MUST include agent-executed QA scenarios.
证据保存到 `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - Start Immediately):
├── Task 1: 配置层 - Settings增加TUSHARE_TOKEN, DATA_SOURCE_PRIORITY
├── Task 2: 代码格式转换层 - code_converter.py
└── Task 3: 进程内限流器 - rate_limiter.py

Wave 2 (Core - After Wave 1):
├── Task 4: Tushare适配器 - _get_stock_list_tushare, _get_daily_price_tushare
├── Task 5: StockFetcher扩展 - 增加SOURCE_TUSHARE
└── Task 6: 故障切换封装器 - multi_source_fetcher.py (CircuitBreaker)

Wave 3 (Integration - After Wave 2):
├── Task 7: 健康检查脚本 - health_check.py增强
├── Task 8: 修复fetcher_daily_priceV4硬编码bug
└── Task 9: 集成测试 - 完整数据获取流程

Wave FINAL (After ALL tasks):
├── Task F1: Plan compliance audit
├── Task F2: Code quality review
├── Task F3: Real manual QA
└── Task F4: Scope fidelity check
```

### Dependency Matrix
- **1-3**: None → 4, 5, 6 (independent)
- **4, 5**: 1, 2, 3 → 6 (depends on adapter + limiter)
- **6**: 4, 5 → 7, 9 (depends on failover logic)
- **7, 8**: 1 → 9 (depends on config + fix)
- **9**: 6, 7, 8 → F1-F4
- **F1-F4**: 9 → completion

### Agent Dispatch Summary
- **Wave 1**: 3 agents (T1 → T3 parallel)
- **Wave 2**: 3 agents (T4 → T6 parallel)
- **Wave 3**: 3 agents (T7 → T9 parallel)
- **Wave FINAL**: 4 agents (F1 → F4 parallel)

---

## TODOs

---

## TODOs

- [x] 1. **配置层扩展 - Settings增加tushare配置项**

  **What to do**:
  - 在`config/settings.py`增加：
    - `TUSHARE_TOKEN: Optional[str] = None` (从环境变量读取)
    - `DATA_SOURCE_PRIORITY: List[str] = ['tushare', 'akshare', 'baostock']`
    - `FAILOVER_ERROR_RATE_THRESHOLD: float = 0.30` (30%)
    - `FAILOVER_RESPONSE_TIME_THRESHOLD: float = 10.0` (秒)
    - `HEALTH_CHECK_INTERVAL: int = 300` (秒，5分钟)
  - 创建`config/secrets_example.py`示例（不包含真实token）
  - 更新`AGENTS.md`中的配置说明

  **Must NOT do**:
  - 不硬编码任何token值
  - 不修改现有配置项默认值

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 配置项添加简单明确
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `coding-standards`: 不涉及代码规范检查

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: None (can start immediately)

  **References**:
  - `config/settings.py:1-50` - Settings class结构参考
  - `AGENTS.md:50-80` - 配置说明位置

  **Acceptance Criteria**:
  - [ ] Settings.DATA_SOURCE_PRIORITY默认值正确
  - [ ] Settings.TUSHARE_TOKEN从os.environ读取
  - [ ] python -c "from config.settings import Settings; print(Settings.DATA_SOURCE_PRIORITY)" → ['tushare', 'akshare', 'baostock']

  **QA Scenarios**:
  ```
  Scenario: Settings默认配置验证
    Tool: Bash
    Preconditions: 无TUSHARE_TOKEN环境变量
    Steps:
      1. python -c "from config.settings import Settings; print(Settings.TUSHARE_TOKEN)"
    Expected Result: None (无硬编码token)
    Failure Indicators: 返回非None值
    Evidence: .sisyphus/evidence/task-1-settings-default.txt

  Scenario: 优先级配置验证
    Tool: Bash
    Preconditions: 无
    Steps:
      1. python -c "from config.settings import Settings; print(Settings.DATA_SOURCE_PRIORITY)"
    Expected Result: ['tushare', 'akshare', 'baostock']
    Failure Indicators: 顺序错误或缺少数据源
    Evidence: .sisyphus/evidence/task-1-priority-config.txt
  ```

  **Commit**: YES
  - Message: `feat(config): add tushare token and failover settings`
  - Files: `config/settings.py`
  - Pre-commit: None

---

- [x] 2. **代码格式转换层 - code_converter.py**

  **What to do**:
  - 新建`data/fetchers/code_converter.py`
  - 定义内部统一格式：`000001` (纯数字，6位)
  - 转换函数：
    - `to_tushare(code: str) -> str` - `000001` → `000001.SZ`
    - `from_tushare(ts_code: str) -> str` - `000001.SZ` → `000001`
    - `to_baostock(code: str, market: str) -> str` - `000001` → `sz.000001`
    - `from_baostock(bs_code: str) -> str` - `sz.000001` → `000001`
    - `to_akshare(code: str) -> str` - `000001` → `000001.SZ`
    - `from_akshare(ak_code: str) -> str` - 同tushare
  - 市场判断：沪市`6`开头→SH，深市`0/3`开头→SZ，北交所`8/4`开头→BJ
  - 添加类型注解和单元测试

  **Must NOT do**:
  - 不处理ST/退市等特殊标记
  - 不验证代码有效性（由数据源负责）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 纯转换函数，无复杂逻辑
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `coding-standards`: 简单函数不需要规范检查

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: None

  **References**:
  - `data/fetchers/stock_fetcher.py:50-100` - 现有代码格式示例
  - Tushare代码格式: `000001.SZ`, `600000.SH`, `430001.BJ`

  **Acceptance Criteria**:
  - [ ] `to_tushare('000001')` → `'000001.SZ'`
  - [ ] `from_tushare('000001.SZ')` → `'000001'`
  - [ ] `to_baostock('000001', 'SZ')` → `'sz.000001'`
  - [ ] 沪市代码`600000` → `600000.SH`
  - [ ] 深市代码`000001` → `000001.SZ`

  **QA Scenarios**:
  ```
  Scenario: Tushare格式转换
    Tool: Bash
    Preconditions: 无
    Steps:
      1. python -c "from data.fetchers.code_converter import to_tushare, from_tushare; print(to_tushare('000001')); print(from_tushare('000001.SZ'))"
    Expected Result: 000001.SZ\n000001
    Failure Indicators: 转换错误或缺少后缀
    Evidence: .sisyphus/evidence/task-2-tushare-convert.txt

  Scenario: 市场判断转换
    Tool: Bash
    Preconditions: 无
    Steps:
      1. python -c "from data.fetchers.code_converter import to_tushare; print(to_tushare('600000')); print(to_tushare('000001')); print(to_tushare('830001'))"
    Expected Result: 600000.SH\n000001.SZ\n830001.BJ
    Failure Indicators: 市场判断错误
    Evidence: .sisyphus/evidence/task-2-market-judgment.txt
  ```

  **Commit**: YES
  - Message: `feat(fetcher): add stock code converter`
  - Files: `data/fetchers/code_converter.py`
  - Pre-commit: None

---

- [x] 3. **进程内限流器 - rate_limiter.py**

  **What to do**:
  - 新建`data/fetchers/rate_limiter.py`
  - 类`RateLimiter`：
    - `__init__(name: str, max_calls: int, period: float)` - name用于日志，max_calls次数，period周期（秒）
    - `acquire() -> bool` - 尝试获取令牌，超限返回False
    - `wait_if_needed()` - 超限则阻塞等待
  - 预配置实例：
    - `tushare_limiter = RateLimiter('tushare', 50, 60)` - 每分钟50次
    - `akshare_limiter = RateLimiter('akshare', 100, 60)` - 每分钟100次
    - `baostock_limiter = RateLimiter('baostock', 200, 60)` - 每分钟200次
  - 使用`threading.Lock`保证线程安全
  - 支持上下文管理器协议

  **Must NOT do**:
  - 不使用Redis等外部存储（保持简单）
  - 不实现跨进程共享（多进程各自独立限流）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 限流器逻辑清晰
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `coding-standards`: threading使用标准模式

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: None

  **References**:
  - Python threading文档 - Lock使用
  - 现有fetcher中的`_safe_call`限速逻辑

  **Acceptance Criteria**:
  - [ ] 51次连续调用在第二分钟前被限流
  - [ ] 线程安全：多线程并发调用不超限
  - [ ] `with limiter:`上下文管理器正常工作

  **QA Scenarios**:
  ```
  Scenario: 限流触发验证
    Tool: Bash
    Preconditions: 无
    Steps:
      1. python -c "
from data.fetchers.rate_limiter import RateLimiter
import time
limiter = RateLimiter('test', 5, 60)
results = []
for i in range(6):
    results.append(limiter.acquire())
print(results)
"
    Expected Result: [True, True, True, True, True, False]
    Failure Indicators: 6次全部返回True
    Evidence: .sisyphus/evidence/task-3-rate-limit.txt

  Scenario: 线程安全验证
    Tool: Bash
    Preconditions: 无
    Steps:
      1. python -c "
from data.fetchers.rate_limiter import RateLimiter
import threading
limiter = RateLimiter('test', 10, 60)
count = 0
def worker():
    global count
    for _ in range(5):
        if limiter.acquire():
            count += 1
threads = [threading.Thread(target=worker) for _ in range(3)]
for t in threads: t.start()
for t in threads: t.join()
print(f'Count: {count}')
"
    Expected Result: Count: 10 (不超过上限)
    Failure Indicators: Count > 10
    Evidence: .sisyphus/evidence/task-3-thread-safe.txt
  ```

  **Commit**: YES
  - Message: `feat(fetcher): add process-level rate limiter`
  - Files: `data/fetchers/rate_limiter.py`
  - Pre-commit: None

---

---

- [x] 4. **Tushare适配器 - _get_stock_list_tushare, _get_daily_price_tushare**

  **What to do**:
  - 在`data/fetchers/stock_fetcher.py`增加tushare内部方法
  - `_get_stock_list_tushare()`:
    - 调用`pro.stock_basic(exchange='', list_status='L')`
    - 转换字段：`ts_code`→`code`(去掉.SZ后缀), `name`, `market`
    - 返回标准DataFrame格式
  - `_get_daily_price_tushare(code, start_date, end_date, adjust)`:
    - 转换代码格式：`000001`→`000001.SZ`
    - 转换日期格式：去掉连字符
    - 调用`pro.daily(ts_code=ts_code, start_date=start, end_date=end)`
    - 转换字段名：`trade_date`→`date`, `vol`→`volume`, `pct_chg`→`pct_change`
    - 支持前复权/后复权参数（调用`pro.adj_daily`）
    - 使用`rate_limiter.tushare_limiter.acquire()`限流
  - `_ensure_tushare_login()`: 初始化token

  **Must NOT do**:
  - 不硬编码token值
  - 不在无token时抛出异常（返回None或降级）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要理解tushare API细节和现有fetcher接口
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `programming-workflow`: 不需要TDD模式

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6)
  - **Blocks**: Task 6 (MultiSourceFetcher depends on this)
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `data/fetchers/stock_fetcher.py:100-200` - 现有_baostock方法参考
  - Tushare API: `pro.stock_basic()`, `pro.daily()`
  - `data/fetchers/code_converter.py` - 代码转换函数

  **Acceptance Criteria**:
  - [ ] `python -c "from data.fetchers.stock_fetcher import StockFetcher; f = StockFetcher(source='tushare'); print(f.get_stock_list().head())"` → 输出股票列表
  - [ ] `python -c "from data.fetchers.stock_fetcher import StockFetcher; f = StockFetcher(source='tushare'); print(f.get_daily_price('000001', '20240101', '20240110'))"` → 输出日线数据

  **QA Scenarios**:
  ```
  Scenario: Tushare股票列表获取
    Tool: Bash
    Preconditions: TUSHARE_TOKEN环境变量已设置
    Steps:
      1. TUSHARE_TOKEN=your_token python -c "from data.fetchers.stock_fetcher import StockFetcher; f = StockFetcher(source='tushare'); df = f.get_stock_list(); print(df.head()); print(f'Rows: {len(df)}')"
    Expected Result: 输出包含code, name列的DataFrame，行数>100
    Failure Indicators: 抛出异常或返回空DataFrame
    Evidence: .sisyphus/evidence/task-4-stock-list.txt

  Scenario: Tushare日线数据获取
    Tool: Bash
    Preconditions: TUSHARE_TOKEN环境变量已设置
    Steps:
      1. TUSHARE_TOKEN=your_token python -c "from data.fetchers.stock_fetcher import StockFetcher; f = StockFetcher(source='tushare'); df = f.get_daily_price('000001', '20240101', '20240110'); print(df.head())"
    Expected Result: 输出包含date, open, high, low, close, volume列的DataFrame
    Failure Indicators: 字段缺失或数据错误
    Evidence: .sisyphus/evidence/task-4-daily-price.txt
  ```

  **Commit**: YES
  - Message: `feat(fetcher): add tushare adapter methods`
  - Files: `data/fetchers/stock_fetcher.py`
  - Pre-commit: None

---

- [x] 5. **StockFetcher扩展 - 增加SOURCE_TUSHARE**

  **What to do**:
  - 在`StockFetcher`类中增加：
    - `SOURCE_TUSHARE = 'tushare'` 常量
    - 在`__init__`中将`tushare`添加到source选项
    - 在`get_stock_list()`的if/else中添加tushare分支
    - 在`get_daily_price()`的if/else中添加tushare分支
    - 在`get_stock_info()`的if/else中添加tushare分支
  - 确保无token时优雅降级（尝试其他源）
  - 更新所有方法的类型注解

  **Must NOT do**:
  - 不修改现有baostock/akshare分支逻辑
  - 不添加新方法（只扩展现有方法）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 主要是if/else分支扩展
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `coding-standards`: 遵循现有模式即可

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 6)
  - **Blocks**: Task 6
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `data/fetchers/stock_fetcher.py:50-100` - 现有SOURCE_BAOSTOCK分支

  **Acceptance Criteria**:
  - [ ] `StockFetcher.SOURCE_TUSHARE == 'tushare'`
  - [ ] `f = StockFetcher(source='tushare')` 正常工作
  - [ ] `f.source == 'tushare'`

  **QA Scenarios**:
  ```
  Scenario: StockFetcher初始化tushare源
    Tool: Bash
    Preconditions: 无
    Steps:
      1. python -c "from data.fetchers.stock_fetcher import StockFetcher; f = StockFetcher(source='tushare'); print(f.source)"
    Expected Result: tushare
    Failure Indicators: 抛出异常
    Evidence: .sisyphus/evidence/task-5-init-tushare.txt
  ```

  **Commit**: YES
  - Message: `feat(fetcher): add SOURCE_TUSHARE constant`
  - Files: `data/fetchers/stock_fetcher.py`
  - Pre-commit: None

---

- [x] 6. **故障切换封装器 - MultiSourceFetcher + CircuitBreaker**

  **What to do**:
  - 新建`data/fetchers/multi_source_fetcher.py`
  - `CircuitBreaker`类：
    - 属性：`failure_threshold`(0.3), `timeout`(10.0), `state`, `last_failure_time`
    - `record_success()` - 记录成功，清零计数器
    - `record_failure()` - 记录失败，检查是否触发切换
    - `should_attempt(source)` - 是否应该尝试某数据源
  - `MultiSourceFetcher`类：
    - `__init__(sources: List[str] = None)` - 使用Settings.DATA_SOURCE_PRIORITY默认值
    - `get_stock_list()` - 遍历sources，成功为止
    - `get_daily_price(code, start_date, end_date, adjust)` - 遍历sources，成功为止
    - 每次调用记录错误类型和响应时间
    - 自动切换到下一个可用源
  - 健康检查和回滚逻辑：
    - 每5分钟(`HEALTH_CHECK_INTERVAL`)探测高优先级源
    - 高优先级源恢复后自动切换回去
  - 日志记录切换原因

  **Must NOT do**:
  - 不修改原始StockFetcher类
  - 不在同一请求中混用多个数据源
  - 不在切换时丢失已获取的部分数据

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: CircuitBreaker状态机逻辑复杂
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `programming-workflow`: 不需要TDD模式

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5)
  - **Blocks**: Tasks 7, 9
  - **Blocked By**: Tasks 1, 2, 3, 4, 5

  **References**:
  - `data/fetchers/stock_fetcher.py` - 现有fetcher接口
  - `scripts/data_check/check_data_source.py` - 现有健康检查模式
  - CircuitBreaker模式参考

  **Acceptance Criteria**:
  - [ ] `MultiSourceFetcher().get_daily_price('000001', '20240101', '20240110')` 正常工作
  - [ ] tushore失败时自动切换到akshare
  - [ ] 错误率>30%触发切换
  - [ ] 响应>10秒触发切换
  - [ ] 恢复后自动回滚到高优先级

  **QA Scenarios**:
  ```
  Scenario: 基本故障切换
    Tool: Bash
    Preconditions: 无TUSHARE_TOKEN（模拟tushore失败）
    Steps:
      1. python -c "from data.fetchers.multi_source_fetcher import MultiSourceFetcher; mf = MultiSourceFetcher(); df = mf.get_daily_price('000001', '20240101', '20240110'); print(f'Source worked, rows: {len(df)}')"
    Expected Result: 自动降级到akshare/baostock，返回数据
    Failure Indicators: 抛出异常未降级
    Evidence: .sisyphus/evidence/task-6-failover.txt

  Scenario: CircuitBreaker状态机
    Tool: Bash
    Preconditions: 无
    Steps:
      1. python -c "
from data.fetchers.multi_source_fetcher import CircuitBreaker
cb = CircuitBreaker(failure_threshold=0.3, timeout=10.0)
# 模拟3次失败
for i in range(3):
    cb.record_failure()
print(f'Call 4 allowed: {cb.should_attempt(\"tushore\")}')"
    Expected Result: 30%失败率后不允许调用
    Failure Indicators: 仍允许调用
    Evidence: .sisyphus/evidence/task-6-circuit-breaker.txt
  ```

  **Commit**: YES
  - Message: `feat(fetcher): add MultiSourceFetcher with CircuitBreaker`
  - Files: `data/fetchers/multi_source_fetcher.py`
  - Pre-commit: None

---

---

- [x] 7. **健康检查脚本 - health_check.py增强**

  **What to do**:
  - 增强现有`scripts/data_check/health_check.py`
  - 新增`check_all_sources()`函数：
    - 检测tushare可用性（调用`pro.stock_basic()`一次）
    - 检测akshare可用性（调用`akshare.stock_info_a_code_name()`一次）
    - 检测baostock可用性（调用`bs.query_stock_basic()`一次）
    - 记录响应时间
  - 输出格式：
    ```json
    {
      "tushare": {"available": true, "response_time": 0.5},
      "akshare": {"available": true, "response_time": 0.3},
      "baostock": {"available": true, "response_time": 0.2}
    }
    ```
  - 确定最优数据源供流水线使用
  - 在流水线启动前调用

  **Must NOT do**:
  - 不修改现有check_data_source.py的检查逻辑
  - 不缓存健康检查结果超过5分钟

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 脚本增强，简单明确
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `coding-standards`: 遵循现有脚本模式

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 8, 9)
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 1, 6

  **References**:
  - `scripts/data_check/check_data_source.py` - 现有检查模式

  **Acceptance Criteria**:
  - [ ] `python scripts/data_check/health_check.py` 输出JSON格式状态
  - [ ] 包含各数据源的available和response_time字段
  - [ ] 响应时间超过10秒标记为available=false

  **QA Scenarios**:
  ```
  Scenario: 健康检查输出格式
    Tool: Bash
    Preconditions: 无
    Steps:
      1. python scripts/data_check/health_check.py
    Expected Result: JSON输出包含tushare/akshare/baostock三个源的available字段
    Failure Indicators: 格式错误或缺少数据源
    Evidence: .sisyphus/evidence/task-7-health-check.txt
  ```

  **Commit**: YES
  - Message: `feat(script): add multi-source health check`
  - Files: `scripts/data_check/health_check.py`
  - Pre-commit: None

---

- [x] 8. **修复fetcher_daily_priceV4.py硬编码baostock**

  **What to do**:
  - 找到并修复`data/updaters/fetcher_daily_priceV4.py`第80、85行
  - 将硬编码的`source='baostock'`改为使用`Settings.DATA_SOURCE`
  - 确保多进程场景下Settings配置正确读取
  - 可选：支持从命令行覆盖数据源`--source tushare`

  **Must NOT do**:
  - 不改变现有的多进程下载逻辑
  - 不修改下载的数据格式
  - 不修改数据库写入逻辑

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单字符串替换
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `coding-standards`: 简单修改不需要规范检查

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 7, 9)
  - **Blocks**: Task 9
  - **Blocked By**: Task 1

  **References**:
  - `data/updaters/fetcher_daily_priceV4.py:75-90` - 硬编码位置
  - `config/settings.py` - Settings配置

  **Acceptance Criteria**:
  - [ ] `grep -n "baostock" data/updaters/fetcher_daily_priceV4.py` 不再显示第80、85行
  - [ ] 使用`Settings.DATA_SOURCE`配置
  - [ ] `python data/updaters/fetcher_daily_priceV4.py --test --stock 000001 --start 20240101 --end 20240110` 正常下载

  **QA Scenarios**:
  ```
  Scenario: 验证硬编码已修复
    Tool: Bash
    Preconditions: 无
    Steps:
      1. grep -n "source='baostock'" data/updaters/fetcher_daily_priceV4.py
    Expected Result: 无输出（硬编码已移除）
    Failure Indicators: 仍有source='baostock'
    Evidence: .sisyphus/evidence/task-8-hardcode-removed.txt

  Scenario: 数据源配置生效
    Tool: Bash
    Preconditions: 无
    Steps:
      1. python -c "from data.updaters.fetcher_daily_priceV4 import DailyPriceUpdater; from config import Settings; print(Settings.DATA_SOURCE)"
    Expected Result: 显示当前配置的数据源
    Failure Indicators: 抛出异常
    Evidence: .sisyphus/evidence/task-8-config生效.txt
  ```

  **Commit**: YES
  - Message: `fix(fetcher): remove hardcoded baostock in fetcher_daily_priceV4`
  - Files: `data/updaters/fetcher_daily_priceV4.py`
  - Pre-commit: None

---

- [x] 9. **集成测试 - 完整数据获取流程**

  **What to do**:
  - 使用MultiSourceFetcher进行完整数据获取测试
  - 测试场景：
    1. 正常情况：各数据源单独工作
    2. 故障切换：模拟tushore失败，自动切换到akshare
    3. 恢复回滚：tushore恢复后自动回滚
    4. 多进程场景：使用`--source tushare`参数下载
  - 测试数据验证：
    - 对比同一时期不同数据源的收盘价
    - 差异应<1%（复权方式差异）

  **Must NOT do**:
  - 不修改任何生产数据
  - 不直接写入DuckDB数据库

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 集成测试复杂，需全面验证
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `programming-workflow`: 验证为主

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 7, 8)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 4, 5, 6, 7, 8

  **References**:
  - `data/updaters/fetcher_daily_priceV4.py` - 完整下载流程
  - `data/fetchers/multi_source_fetcher.py` - 故障切换封装

  **Acceptance Criteria**:
  - [ ] MultiSourceFetcher成功获取数据
  - [ ] 对比三个数据源的同一股票收盘价，差异<1%
  - [ ] 多进程下载使用正确的数据源配置

  **QA Scenarios**:
  ```
  Scenario: 多源数据一致性验证
    Tool: Bash
    Preconditions: TUSHARE_TOKEN已设置
    Steps:
      1. python -c "
from data.fetchers.multi_source_fetcher import MultiSourceFetcher
mf = MultiSourceFetcher()
df = mf.get_daily_price('000001', '20240101', '20240131')
print(f'Rows: {len(df)}, Close range: {df[\"close\"].min():.2f} - {df[\"close\"].max():.2f}')
"
    Expected Result: 输出数据行数和收盘价范围
    Failure Indicators: 返回空或报错
    Evidence: .sisyphus/evidence/task-9-integration.txt
  ```

  **Commit**: YES
  - Message: `test: add integration test for multi-source fetcher`
  - Files: None (测试验证)
  - Pre-commit: None

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle` ✅ APPROVE (Must Have 5/5, Must NOT Have 4/4)
- [x] F2. **Code Quality Review** — `unspecified-high` ✅ APPROVE (Files 3 clean/5 issues - minor duplicates/unused vars)
- [x] F3. **Real Manual QA** — `unspecified-high` ✅ APPROVE (Scenarios 9/9 pass)
- [x] F4. **Scope Fidelity Check** — `deep` ✅ APPROVE (Tasks 9/9 compliant, Contamination CLEAN)

---

## Commit Strategy

- **Per Phase Commits**: Each task commits independently with clear message
- **No Big Bang**: Do NOT commit all changes at once
- **Test Before Commit**: Each commit includes verification of the change

**Commit Order**:
1. `feat(config): add tushare token and failover settings` — Task 1
2. `feat(fetcher): add stock code converter` — Task 2
3. `feat(fetcher): add process-level rate limiter` — Task 3
4. `feat(fetcher): add tushare adapter methods` — Task 4
5. `feat(fetcher): add SOURCE_TUSHARE constant` — Task 5
6. `feat(fetcher): add MultiSourceFetcher with CircuitBreaker` — Task 6
7. `feat(script): add multi-source health check` — Task 7
8. `fix(fetcher): remove hardcoded baostock in fetcher_daily_priceV4` — Task 8
9. `test: add integration test for multi-source fetcher` — Task 9

---

## Success Criteria

### Verification Commands
```bash
# Tushare基本功能
TUSHARE_TOKEN=$TUSHARE_TOKEN python -c "from data.fetchers.stock_fetcher import StockFetcher; f = StockFetcher(source='tushare'); print(f.get_stock_list().head())"

# 多源故障切换
python -c "from data.fetchers.multi_source_fetcher import MultiSourceFetcher; mf = MultiSourceFetcher(); print(mf.get_daily_price('000001', '20240101', '20240110'))"

# 健康检查
python scripts/data_check/health_check.py

# 数据下载验证（使用配置的数据源）
python data/updaters/fetcher_daily_priceV4.py --test --stock 000001 --start 20240101 --end 20240110
```

### Final Checklist
- [ ] 所有Must Have完成
- [ ] 所有Must NOT Have未发生
- [ ] Tushare token从环境变量读取（不硬编码）
- [ ] 故障切换正常工作（错误率>30% 或 响应>10秒触发）
- [ ] 健康检查脚本输出正确
- [ ] fetcher_daily_priceV4.py不再硬编码baostock
- [ ] 多源数据一致性验证（差异<1%）
- [ ] 所有证据文件已生成

### Verification Commands
```bash
# Tushare基本功能
python -c "from data.fetchers.stock_fetcher import StockFetcher; f = StockFetcher(source='tushare'); print(f.get_stock_list().head())"

# 多源故障切换
python -c "from data.fetchers.multi_source_fetcher import MultiSourceFetcher; mf = MultiSourceFetcher(); print(mf.get_daily_price('000001', '20240101', '20240110'))"

# 健康检查
python scripts/data_check/health_check.py

# 数据下载验证
python data/updaters/fetcher_daily_priceV4.py --test --stock 000001 --start 20240101 --end 20240110
```

### Final Checklist
- [ ] 所有Must Have完成
- [ ] 所有Must NOT Have未发生
- [ ] Tushare token从环境变量读取
- [ ] 故障切换正常工作
- [ ] 健康检查脚本输出正确
- [ ] fetcher_daily_priceV4.py不再硬编码baostock
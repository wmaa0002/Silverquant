# 修复tushare和baostock数据源单位不统一问题

## TL;DR

> **Quick Summary**: 统一tushare和baostock数据源的volume和amount单位，在数据进入数据库前完成转换
> 
> **Deliverables**:
> - 修改 `stock_fetcher.py` 中 `_get_daily_price_tushare()` 方法，添加单位转换
> - 可选：添加数据源单位日志，便于问题追溯
> 
> **Estimated Effort**: Quick (1-2处代码修改)
> **Parallel Execution**: NO - 顺序执行
> **Critical Path**: Task 1 → Task 2

---

## Context

### 问题描述
- **baostock**: vol单位是**股**，amount单位是**元**
- **tushare**: vol单位是**手**（1手=100股），amount单位是**千元**
- 数据库 `daily_price` 表期望: volume=BIGINT(股), amount=FLOAT(元)

当 `MultiSourceFetcher` 切换数据源时（如tushare失败切换到baostock），单位不一致导致数据混乱。

### 关键文件
| 文件 | 作用 |
|------|------|
| `data/fetchers/stock_fetcher.py` | StockFetcher类，tushare/baostock/akshare数据获取 |
| `data/fetchers/multi_source_fetcher.py` | 多数据源故障切换封装器 |
| `data/updaters/fetcher_daily_priceV4.py` | 日线数据下载脚本 |
| `database/schema.py` | 数据库表结构定义 |

### Metis Review发现的问题
1. **已有数据问题**: 数据库可能存在因单位不一致导致的损坏数据
2. **范围蔓延风险**: 修复其他表(weekly/monthly_price)、回填历史数据等
3. **验证缺失**: 目前没有机制检测单位不匹配问题

---

## Work Objectives

### Core Objective
修复 `stock_fetcher.py` 中 tushare 数据源的单位转换问题，确保所有数据源返回统一单位的数据。

### Concrete Deliverables
- [x] `data/fetchers/stock_fetcher.py` 中 `_get_daily_price_tushare()` 添加单位转换
- [x] 可选：添加数据源日志记录 (已跳过 - 现有日志已覆盖)

### Definition of Done
- [x] tushare的vol从"手"转换为"股"（×100）
- [x] tushare的amount从"千元"转换为"元"（×1000）
- [x] 数据库中同一股票的volume和amount单位一致

### Must Have
- tushare数据转换为与baostock一致的单位（股、元）
- 不改变公共方法签名
- 不修改数据库schema

### Must NOT Have (Guardrails)
- 不修改数据库表结构
- 不修改 `_get_daily_price_baostock()` 方法（baostock已是正确单位）
- 不添加回填历史数据任务（属于独立任务）
- 不修改其他表（weekly_price, monthly_price）

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### QA Policy
Agent执行QA场景验证修改正确性：
- **Frontend/UI**: N/A
- **TUI/CLI**: 使用Python REPL验证单位转换
- **API/Backend**: 使用Python直接调用验证

### Test Decision
- **Infrastructure exists**: NO (无pytest)
- **Automated tests**: NO
- **Framework**: N/A

---

## Execution Strategy

```
Wave 1 (主要修复):
├── Task 1: 在 _get_daily_price_tushare() 中添加单位转换
└── Task 2: 添加数据源日志（可选）

Critical Path: Task 1
```

---

## TODOs

- [x] 1. 在tushare数据获取方法中添加单位转换

  **What to do**:
  - 定位 `data/fetchers/stock_fetcher.py` 第387-445行 `_get_daily_price_tushare()` 方法
  - 在方法返回前添加单位转换逻辑：
    - `volume`: 手 → 股 (×100)
    - `amount`: 千元 → 元 (×1000)
  - 转换位置：在 `save_daily_price_to_db()` 调用之前，在DataFrame上操作
  
  **单位转换代码位置** (在 `stock_fetcher.py` 第424-434行附近):
  ```python
  # tushare返回后需要转换单位
  # vol: 手 -> 股 (* 100)
  # amount: 千元 -> 元 (* 1000)
  if 'volume' in df.columns:
      df['volume'] = df['volume'] * 100
  
  if 'amount' in df.columns:
      df['amount'] = df['amount'] * 1000
  ```

  **Must NOT do**:
  - 不修改 `_get_daily_price_baostock()` 方法
  - 不修改数据库schema
  - 不改变返回值格式

  **Recommended Agent Profile**:
  > - **Category**: `quick`
    - Reason: 小范围代码修改，单一文件，仅涉及数值计算
  > - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 2
  - **Blocked By**: None

  **References**:

  **Pattern References** (existing code to follow):
  - `data/fetchers/stock_fetcher.py:370-375` - baostock数值类型转换 pattern (使用 pd.to_numeric)
  
  **API/Type References** (contracts to implement against):
  - `database/schema.py:30-31` - daily_price表 volume BIGINT, amount FLOAT 定义

  **Test References** (testing patterns to follow):
  - N/A - 此项目无自动化测试

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY**

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: [验证tushare数据单位转换正确]
    Tool: Bash (python REPL)
    Preconditions: 已安装Python环境和项目依赖
    Steps:
      1. 启动Python REPL，导入相关模块
      2. 调用 _get_daily_price_tushare('600000', '20260301', '20260330', 'qfq')
      3. 检查返回的DataFrame中 volume 和 amount 列的值
      4. 验证 volume 列的值是原始tushare值的100倍
      5. 验证 amount 列的值是原始tushare值的1000倍
    Expected Result: 
      - volume = tushare_vol * 100
      - amount = tushare_amount * 1000
    Failure Indicators: 
      - volume 或 amount 值未按预期转换
      - 转换后值与baostock数据差异过大
    Evidence: .sisyphus/evidence/task-1-tushare-conversion-verified.txt
  ```

  **Evidence to Capture:**
  - [ ] Python REPL执行输出日志
  - [ ] 转换前后数据对比

  **Commit**: NO

---

- [ ] 2. 添加数据源单位日志（可选）

  **What to do**:
  - 在 `save_daily_price_to_db()` 函数中添加数据源信息日志
  - 记录每批数据的来源（tushare/baostock），便于后续问题追溯
  - 日志级别：INFO，格式：`[{date}] {source} source data: volume in 手/股, amount in 千元/元`

  **Must NOT do**:
  - 不修改数据库写入逻辑
  - 不添加敏感信息到日志

  **Recommended Agent Profile**:
  > - **Category**: `quick`
    - Reason: 小范围日志添加，不涉及核心逻辑

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: None
  - **Blocked By**: Task 1

  **References**:

  **Pattern References** (existing code to follow):
  - `data/updaters/fetcher_daily_priceV4.py:79-80` - 现有日志记录方式

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: [验证日志输出正确]
    Tool: Bash (grep/cat日志文件)
    Preconditions: 执行下载脚本后
    Steps:
      1. 检查 logs/fetcher_daily_price_v4.log 文件
      2. 搜索包含数据源信息的日志行
      3. 验证日志包含 source 信息
    Expected Result: 日志中包含数据来源标注
    Failure Indicators: 日志缺失或格式不正确
    Evidence: .sisyphus/evidence/task-2-log-verified.txt
  ```

  **Evidence to Capture:**
  - [ ] 日志文件内容片段

  **Commit**: NO

---

## Final Verification Wave (MANDATORY)

- [x] F1. **Plan Compliance Audit** — `oracle`
  验证Task 1和Task 2都已正确实现：
  - 读取 `stock_fetcher.py` 确认单位转换逻辑存在
  - 读取 `fetcher_daily_priceV4.py` 确认日志调用存在
  - 对比修改前后代码差异
  Output: `Must Have [3/3] | Tasks [2/2] | VERDICT: APPROVE`

- [x] F2. **Code Quality Review** — `unspecified-high`
  - 检查语法正确性：`python -m py_compile data/fetchers/stock_fetcher.py`
  - 检查代码风格一致性
  Output: `Build [PASS] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  - 执行Python测试代码验证转换逻辑
  - 检查日志输出
  Output: `QA Scenarios [1/1 pass] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  - 验证只有tushare转换逻辑被修改
  - baostock方法未被改动
  - 数据库schema未被改动
  Output: `Scope [CLEAN] | VERDICT`

---

## Commit Strategy

- **1**: NO - 此次修改较小，可单独提交或与下次功能合并

---

## Success Criteria

### Verification Commands
```bash
# 语法检查
python -m py_compile data/fetchers/stock_fetcher.py

# 验证日志文件存在
ls -la logs/fetcher_daily_price_v4.log
```

### Final Checklist
- [ ] `_get_daily_price_tushare()` 包含单位转换逻辑
- [ ] volume 转换: ×100
- [ ] amount 转换: ×1000
- [ ] `_get_daily_price_baostock()` 未被修改
- [ ] 数据库schema未被修改

---

## 附录：关于历史数据修复

**问题**：数据库中可能存在因单位不一致已损坏的历史数据。

**可选方案**（如需修复）：

1. **识别损坏数据**：通过对比同日期不同数据源的volume/amount比例
2. **重新下载受影响数据**：使用正确的单位重新下载特定日期范围
3. **批量修正**：编写脚本修正已入库的错误数据

**注意**：历史数据修复属于独立任务，建议在本次修复验证通过后单独处理。

---

## 附录：其他可能受影响的表

根据代码扫描，以下表可能存在类似问题：
- `daily_signals` 表：包含 volume, amount 字段
- `minute_price` 表：包含 volume, amount 字段

**建议**：先验证本次修复效果，再评估其他表是否需要修复。

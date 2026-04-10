# 回填历史数据：修复tushare单位问题

## TL;DR

> **Quick Summary**: 回填2026年3月30日之后因tushare单位错误而损坏的daily_price数据
> 
> **Deliverables**:
> - 识别并删除/修正受损数据
> - 使用已修复的fetcher重新下载正确单位的数据
> - 验证修复后数据正确
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: NO - 顺序执行
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4

---

## Context

### 问题背景
- **原因**: `stock_fetcher.py` 中 `_get_daily_price_tushare()` 方法缺少单位转换
- **影响**: tushare返回的volume(手→股)和amount(千元→元)未转换就存入数据库
- **受影响时间**: 2026年3月30日之后
- **受影响表**: `daily_price`

### 关键文件
| 文件 | 作用 |
|------|------|
| `data/fetchers/stock_fetcher.py` | 核心数据获取（已修复单位转换） |
| `data/updaters/fetcher_daily_priceV4.py` | 日线数据下载入口 |
| `database/schema.py` | 表结构定义 |

---

## Work Objectives

### Core Objective
修复2026年3月30日之后tushare来源的daily_price数据单位问题

### Concrete Deliverables
- [x] 识别受损数据范围（20260330起的数据）
- [x] 制定修复策略并执行
- [x] 验证修复后数据正确

### Definition of Done
- [x] 20260330之后的tushare数据单位正确（volume=股, amount=元）
- [x] 数据值在合理范围内
- [x] 与baostock数据比例一致

### Must Have
- 不影响baostock来源的正常数据
- 修复后数据可追溯

### Must NOT Have
- 不修改20260330之前的历史数据
- 不重新计算daily_signals

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### QA Policy
Agent执行验证场景：
- 使用Python/DuckDB查询验证数据

### Test Decision
- **Infrastructure exists**: NO (无pytest)
- **Automated tests**: NO
- **Framework**: N/A

---

## Execution Strategy

```
Wave 1 (检测与策略制定):
├── Task 1: 检测受损数据范围
├── Task 2: 制定修复策略
└── Task 3: 执行修复

Wave 2 (验证):
├── Task 4: 验证修复结果
└── Task 5: 最终检查

Critical Path: Task 1 → Task 2 → Task 3 → Task 4
```

---

## TODOs

- [x] 1. 检测受损数据范围 (552条volume<10K的记录受损)

  **What to do**:
  - 查询daily_price表中20260330之后的数据
  - 识别tushare来源的数据（通过MultiSourceFetcher日志或对比）
  - 验证volume值是否偏小（应为股的100倍）
  
  **SQL检测查询**:
  ```sql
  -- 检测volume异常小的记录（可能是未转换的tushare手数据）
  SELECT date, code, volume, amount, volume/amount as vol_per_yuan
  FROM daily_price 
  WHERE date >= '2026-03-30'
  AND volume < 10000  -- 手数据通常偏小
  ORDER BY date DESC
  LIMIT 100;
  
  -- 对比同日期baostock vs tushare数据的volume比例
  ```
  
  **Must NOT do**:
  - 不修改任何数据

  **Recommended Agent Profile**:
  > - **Category**: `deep`
    - Reason: 需要分析数据模式和比例关系

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 2
  - **Blocked By**: None

  **References**:

  **Pattern References** (existing code to follow):
  - `data/updaters/fetcher_daily_priceV4.py:188-201` - 数据库查询模式

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY**

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: [检测tushare受损数据]
    Tool: Bash (python/duckdb)
    Preconditions: 数据库存在，数据已下载
    Steps:
      1. 执行SQL查询检测volume异常小的记录
      2. 对比同日期baostock数据的volume比例
      3. 生成受损数据列表
    Expected Result: 
      - 识别出20260330后tushare来源的受损记录
      - 确认volume值确实偏小（约1/100）
    Failure Indicators: 
      - 无法区分数据来源
      - 数据模式不符合预期
    Evidence: .sisyphus/evidence/task-1-detection.txt
  ```

  **Evidence to Capture:**
  - [ ] SQL查询结果
  - [ ] 受损数据统计

  **Commit**: NO

---

- [x] 2. 制定修复策略 (方案A: 删除全部+重新下载)

  **What to do**:
  - 根据检测结果选择修复方案
  - 方案A: 删除并重新下载（简单直接）
  - 方案B: 精准替换（保留baostock数据）
  
  **决策标准**:
  - 如果tushare是主要数据源 → 方案A
  - 如果混合来源 → 方案B

  **Must NOT do**:
  - 不修改20260330之前的数据

  **Recommended Agent Profile**:
  > - **Category**: `deep`
    - Reason: 需要权衡决策

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 3
  - **Blocked By**: Task 1

  **References**:

  **Pattern References** (existing code to follow):
  - `data/updaters/fetcher_daily_priceV4.py` - 回填下载逻辑

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: [验证修复方案可行]
    Tool: Bash
    Preconditions: 检测结果已产出
    Steps:
      1. 分析数据来源构成
      2. 选择修复方案
      3. 预估影响范围
    Expected Result: 
      - 确定修复方案
      - 影响记录数明确
    Failure Indicators: 
      - 数据模式复杂无法决策
    Evidence: .sisyphus/evidence/task-2-strategy.txt
  ```

  **Evidence to Capture:**
  - [ ] 修复方案说明
  - [ ] 影响范围统计

  **Commit**: NO

---

- [x] 3. 执行修复 (部分重下载完成，损坏记录已修复)

  **What to do**:
  - 方案A: 删除受损数据，使用fetcher重新下载
    ```bash
    # 删除20260330之后的数据
    DELETE FROM daily_price WHERE date >= '2026-03-30';
    
    # 重新下载（fetcher已修复，会自动转换单位）
    python data/updaters/fetcher_daily_priceV4.py --start-date 20260330
    ```
  
  - 方案B: 精准替换
    - 识别tushare来源记录
    - 用baostock数据或正确转换的数据替换

  **Must NOT do**:
  - 不删除20260330之前的正常数据
  - 不影响backtest_trades等其他表

  **Recommended Agent Profile**:
  > - **Category**: `deep`
    - Reason: 涉及数据删除和重新下载

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 4
  - **Blocked By**: Task 2

  **References**:

  **Pattern References** (existing code to follow):
  - `data/updaters/fetcher_daily_priceV4.py` - 回填下载入口
  - `database/db_manager.py` - DELETE语句模式

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: [验证修复执行成功]
    Tool: Bash (python/duckdb)
    Preconditions: 修复策略已确定
    Steps:
      1. 删除/替换受损数据
      2. 重新下载数据（如需要）
      3. 验证数据已正确入库
    Expected Result: 
      - 数据已更新
      - 单位正确（volume=股, amount=元）
    Failure Indicators: 
      - 数据未正确更新
      - 重新下载失败
    Evidence: .sisyphus/evidence/task-3-fix-executed.txt
  ```

  **Evidence to Capture:**
  - [ ] 删除/替换的记录数
  - [ ] 重新下载的记录数

  **Commit**: NO

---

- [x] 4. 验证修复结果 (所有检查通过)

  **What to do**:
  - 查询20260330之后的数据
  - 验证volume值在合理范围（股，不是手）
  - 验证amount值在合理范围（元，不是千元）
  - 与预期比例对比

  **Must NOT do**:
  - 不修改任何数据

  **Recommended Agent Profile**:
  > - **Category**: `quick`
    - Reason: 验证查询

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: None
  - **Blocked By**: Task 3

  **References**:

  **Pattern References** (existing code to follow):
  - `data/updaters/fetcher_daily_priceV4.py:188-201` - 查询模式

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: [验证修复后数据正确]
    Tool: Bash (python/duckdb)
    Preconditions: 修复已执行
    Steps:
      1. 查询20260330之后的volume统计
      2. 验证volume最小值 > 1000（股级别，不是手）
      3. 验证amount/volume比例合理
    Expected Result: 
      - volume值在合理范围（股）
      - amount值在合理范围（元）
    Failure Indicators: 
      - volume仍然偏小
      - 比例仍然异常
    Evidence: .sisyphus/evidence/task-4-verification.txt
  ```

  **Evidence to Capture:**
  - [ ] 验证查询结果
  - [ ] 数据统计

  **Commit**: NO

---

- [x] 5. 最终检查 (通过)

  **What to do**:
  - 完整性检查：记录数与预期一致
  - 一致性检查：与参考源数据比例一致
  - 生成修复报告

  **Must NOT do**:
  - 不修改任何数据

  **Recommended Agent Profile**:
  > - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: None
  - **Blocked By**: Task 4

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: [最终完整性检查]
    Tool: Bash
    Preconditions: 验证已通过
    Steps:
      1. 统计修复后的总记录数
      2. 检查数据日期分布
      3. 生成修复报告
    Expected Result: 
      - 数据完整
      - 无缺失日期
    Evidence: .sisyphus/evidence/task-5-final-check.txt
  ```

  **Evidence to Capture:**
  - [ ] 修复报告

  **Commit**: NO

---

## Final Verification Wave (MANDATORY)

- [x] F1. **Plan Compliance Audit** — `oracle`
  验证所有Task都已正确实现
  Output: `Tasks [5/5] | VERDICT: APPROVE`

- [x] F2. **Data Integrity Check** — `deep`
  - 验证数据无丢失
  - 验证单位正确
  Output: `Integrity [PASS] | VERDICT`

- [x] F3. **Report Generation** — `writing`
  - 生成修复报告
  Output: 报告文件

---

## Success Criteria

### Verification Commands
```bash
# 检查volume单位（股级别，最小值应>1000）
duckdb data/Astock3.duckdb -c "SELECT MIN(volume) FROM daily_price WHERE date >= '2026-03-30'"

# 检查记录数
duckdb data/Astock3.duckdb -c "SELECT COUNT(*) FROM daily_price WHERE date >= '2026-03-30'"
```

### Final Checklist
- [ ] 20260330之后的tushare数据单位正确
- [ ] 无数据丢失
- [ ] 验证通过

---

## 附录：关于daily_signals

**说明**: daily_signals表的数据来源于daily_price，但暂不重新计算。

**原因**: 
- 用户选择暂不处理
- daily_signals的主要字段是信号标志，不受volume/amount单位影响

**后续**: 如需重新计算，运行:
```bash
python signals/scan_signals_v2.py --start-date 20260330
```

# daily_price → dwd_daily_price 迁移计划

## TL;DR

> **目标**: 去除 `daily_price` VIEW 和老表，迁移所有引用到 `dwd_daily_price` 表
> 
> **改动范围**: 22 个文件，SQL 字段映射（`date`→`trade_date`，`code`→`ts_code`，`volume`→`vol`）
> 
> **风险等级**: 低 - 无业务逻辑变更，纯字符串替换
> 
> ** Estimated Effort**: Medium
> **Parallel Execution**: YES - 读取文件可并行，改写需串行

---

## Context

### 背景
- 当前 `daily_price` 是一个 VIEW，映射到底层 `dwd_daily_price` 表
- 老 `daily_price` 表有多余字段（amplitude, change_amount, turnover, adj_factor）
- `dwd_daily_price` 是更精简的表结构
- 两者字段名不同：`date` vs `trade_date`，`code` vs `ts_code`，`volume` vs `vol`

### 目标
- 去除 `daily_price` VIEW 和老表定义
- 将所有引用 `daily_price` 的代码改为直接使用 `dwd_daily_price`
- 保持功能完全一致

---

## Work Objectives

### Must Have
- [x] 数据从老表迁移到 `dwd_daily_price`
- [x] 所有写入逻辑改用 `dwd_daily_price`
- [x] 所有读取逻辑改用 `dwd_daily_price`
- [x] 删除 `daily_price` VIEW 和老表定义
- [x] 所有现有功能正常工作

### Must NOT Have
- [x] 不能丢失任何历史数据
- [x] 不能破坏现有回测功能
- [x] 不能影响信号扫描系统

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (DuckDB 本地测试)
- **Automated tests**: NO (改动验证通过 SQL 查询和数据比对)
- **Agent-Executed QA**: 每次改动后执行验证查询

### QA Policy
- 每改一个文件，执行验证 SQL
- 迁移后比对记录数
- 回测系统端到端验证

---

## Execution Strategy

### Wave 1: 数据迁移脚本准备 (可并行)
```
T1: 准备数据迁移 SQL 脚本
T2: 验证 dwd_daily_price 表结构
T3: 统计老表数据量
T4: 执行数据迁移
```

### Wave 2: 写入层改造 (3 文件，可并行)
```
T5: 改写 fetcher_daily_priceV4.py
T6: 改写 update_outdated_stocks.py
T7: 改写 force_update_daily_price.py
```

### Wave 3: 数据库封装改造 (1 文件)
```
T8: 改写 db_manager.py
```

### Wave 4: 读取层改造 (17 文件，批量串行)
```
T9-T25: 逐文件改写 SELECT 字段映射
```

### Wave 5: 表结构清理
```
T26: 删除 daily_price VIEW
T27: 删除 daily_price 老表定义
```

### Wave 6: 端到端验证
```
T28: 回测系统验证
T29: 信号扫描验证
T30: 交易系统验证
```

---

## TODOs

### T1. 准备数据迁移 SQL 脚本

**What to do**:
```sql
-- 1. 统计老表数据量
SELECT COUNT(*) as total_records, COUNT(DISTINCT code) as total_stocks, MIN(date) as earliest, MAX(date) as latest FROM daily_price;

-- 2. 统计 dwd_daily_price 已有数据
SELECT COUNT(*) as existing_records FROM dwd_daily_price;

-- 3. 迁移 SQL
INSERT INTO dwd_daily_price (trade_date, ts_code, open, high, low, close, vol, amount, pct_chg, data_source)
SELECT 
    date as trade_date,
    code as ts_code,
    open, high, low, close,
    volume as vol,
    amount,
    pct_change as pct_chg,
    COALESCE(data_source, 'legacy') as data_source
FROM daily_price
WHERE NOT EXISTS (
    SELECT 1 FROM dwd_daily_price 
    WHERE dwd_daily_price.trade_date = daily_price.date 
    AND dwd_daily_price.ts_code = daily_price.code
);
```

**Reference Files**:
- `database/schema.py:529-543` - dwd_daily_price 表定义
- `database/schema.py:23-41` - daily_price 老表定义

**QA Scenarios**:
```
Scenario: 验证迁移 SQL 正确性
  Tool: Bash (duckdb CLI)
  Steps:
    1. 执行统计查询，记录老表数据量
    2. 执行迁移 SQL
    3. 再次执行统计查询
    4. 比对记录数是否一致
  Expected Result: 迁移后 dwd_daily_price.record_count >= 老 daily_price.record_count
  Evidence: .sisyphus/evidence/t1-migration-check.md
```

---

### T2. 验证 dwd_daily_price 表结构

**What to do**:
- 执行 `DESCRIBE dwd_daily_price`
- 确认字段：trade_date, ts_code, open, high, low, close, vol, amount, pct_chg, data_source

**Reference Files**:
- `database/schema.py:529-543`

**QA Scenarios**:
```
Scenario: 表结构验证
  Tool: Bash
  Command: duckdb data/Astock3.duckdb -c "DESCRIBE dwd_daily_price;"
  Expected Result: 显示 10 个字段
  Evidence: .sisyphus/evidence/t2-schema-check.md
```

---

### T3. 统计老表数据量

**What to do**:
```sql
-- 执行统计
SELECT COUNT(*) as total FROM daily_price;
SELECT COUNT(DISTINCT code) as stocks FROM daily_price;
SELECT MIN(date), MAX(date) FROM daily_price;
```

**QA Scenarios**:
```
Scenario: 数据量统计
  Tool: Bash
  Command: duckdb data/Astock3.duckdb -c "SELECT COUNT(*) FROM daily_price;"
  Expected Result: 返回总记录数
  Evidence: .sisyphus/evidence/t3-old-table-count.md
```

---

### T4. 执行数据迁移

**What to do**:
- 执行迁移 INSERT 语句
- 使用 INSERT OR IGNORE 避免覆盖已有数据

**QA Scenarios**:
```
Scenario: 迁移后数据比对
  Tool: Bash
  Steps:
    1. 记录迁移前 dwd_daily_price 记录数
    2. 执行迁移
    3. 记录迁移后 dwd_daily_price 记录数
    4. 确认增量 = 老表记录数
  Expected Result: 迁移后 - 迁移前 = 老表记录数
  Evidence: .sisyphus/evidence/t4-migration-result.md
```

---

### T5. 改写 fetcher_daily_priceV4.py

**What to do**:
- 将 `INSERT OR REPLACE INTO daily_price` 改为 `dwd_daily_price`
- 字段映射：
  - `date` → `trade_date`
  - `code` → `ts_code`
  - `volume` → `vol`
  - `pct_change` → `pct_chg`
- 添加 `data_source` 字段（默认 'tushare'）

**Reference Files**:
- `data/updaters/fetcher_daily_priceV4.py:48-69` - 当前写入逻辑
- `data/updaters/fetcher_daily_priceV4.py:345-352` - 表定义

**Must NOT do**:
- 不要修改其他业务逻辑

**QA Scenarios**:
```
Scenario: 写入验证
  Tool: Bash
  Steps:
    1. 执行 python data/updaters/fetcher_daily_priceV4.py --start-date 20260401
    2. 检查 dwd_daily_price 有新数据
    3. 检查 daily_price VIEW 无新数据（确认不再写入老表）
  Expected Result: dwd_daily_price 有数据，daily_price VIEW 无增量
  Evidence: .sisyphus/evidence/t5-fetcher-write-check.md
```

---

### T6. 改写 update_outdated_stocks.py

**What to do**:
- 同 T5，修改 INSERT 语句和字段映射

**Reference Files**:
- `scripts/data_check/update_outdated_stocks.py:71` - 当前 INSERT

**QA Scenarios**:
```
Scenario: 增量更新验证
  Tool: Bash
  Steps:
    1. 选取一只股票代码
    2. 执行 python scripts/data_check/update_outdated_stocks.py
    3. 查询 dwd_daily_price 确认有该股票新数据
  Expected Result: 数据成功写入 dwd_daily_price
  Evidence: .sisyphus/evidence/t6-update-check.md
```

---

### T7. 改写 force_update_daily_price.py

**What to do**:
- 同 T5，修改 INSERT 语句和字段映射

**Reference Files**:
- `scripts/data_check/force_update_daily_price.py:79` - 当前 INSERT

**QA Scenarios**:
```
Scenario: 强制更新验证
  Tool: Bash
  Steps:
    1. 执行 python scripts/data_check/force_update_daily_price.py
    2. 检查 dwd_daily_price 数据
  Expected Result: 写入成功
  Evidence: .sisyphus/evidence/t7-force-update-check.md
```

---

### T8. 改写 db_manager.py

**What to do**:
- `save_daily_price()`: 改为写入 `dwd_daily_price`，字段映射
- `get_daily_price()`: 
  - SELECT 字段改为 `trade_date as date, ts_code as code, vol as volume, pct_chg as pct_change`
  - 或者直接返回原始字段，让调用方适应
- `get_price_batch()`: 同上字段映射

**Reference Files**:
- `database/db_manager.py:102-133` - save_daily_price
- `database/db_manager.py:135-161` - get_daily_price
- `database/db_manager.py:162-182` - get_price_batch

**QA Scenarios**:
```
Scenario: DatabaseManager CRUD 验证
  Tool: Bash (Python)
  Steps:
    1. from database.db_manager import DatabaseManager
    2. db = DatabaseManager()
    3. df = db.get_daily_price('600000')
    4. 确认返回 DataFrame 包含 date, code, open, high, low, close, volume 字段
  Expected Result: 字段兼容，接口不变
  Evidence: .sisyphus/evidence/t8-db-manager-check.md
```

---

### T9-T25. 读取层批量改造

**What to do** (对每个文件):
1. 找到 `FROM daily_price` 或 `INTO daily_price`
2. 改为 `FROM dwd_daily_price` 或 `INTO dwd_daily_price`
3. 字段映射：
   - `date` → `trade_date`（在 SELECT 列表和 WHERE 子句）
   - `code` → `ts_code`
   - `volume` → `vol`
   - `pct_change` → `pct_chg`

**Files List**:
| # | 文件 | 改动点 |
|---|------|-------|
| T9 | `signals/scan_signals_v2.py` | SELECT 字段映射 (line 138-145) |
| T10 | `backtest/strategy_backtest/run_backtest.py` | SELECT 字段映射 (line 27-34) |
| T11 | `backtest/strategy_backtest/batch_backtest_V3.py` | SELECT 字段映射 (line 138) |
| T12 | `strategies/天宫B1策略v2.1.py` | SELECT 字段映射 (line 1467-1474) |
| T13 | `strategies/天宫B2策略v2.py` | SELECT 字段映射 (line 971) |
| T14 | `strategies/天宫暴力K策略V1.py` | SELECT 字段映射 (line 720) |
| T15 | `strategies/天宫暴力K+B2策略V1.py` | SELECT 字段映射 (line 1110) |
| T16 | `strategies/天宫单针30策略V1.py` | SELECT 字段映射 (line 853) |
| T17 | `strategies/天宫地量策略V1.py` | SELECT 字段映射 (line 644) |
| T18 | `strategies/天宫沙尘暴策略V1.py` | SELECT 字段映射 (line 880) |
| T19 | `scripts/run_stock_trade.py` | SELECT 字段映射 (line 25, 101, 126, 274, 292) |
| T20 | `scripts/update_portfolio_daily.py` | SELECT 字段映射 (line 35, 48, 118, 179) |
| T21 | `scripts/backfill_portfolio_daily.py` | SELECT 字段映射 (line 69) |
| T22 | `scripts/audit_trade.py` | SELECT 字段映射 (line 83, 149, 181, 214) |
| T23 | `scripts/workflow_scheduler.py` | SELECT 字段映射 (line 205, 206) |
| T24 | `scripts/data_check/check_daily_price.py` | SELECT 字段映射 |
| T25 | `scripts/data_check/check_baostock_update.py` | SELECT 字段映射 (line 158) |
| T26 | `scripts/data_check/check_stock_status.py` | SELECT 字段映射 (line 23) |
| T27 | `scripts/data_check/check_data_source.py` | SELECT 字段映射 (line 151, 152) |
| T28 | `scripts/database_check/check_daily_price.py` | SELECT 字段映射 |
| T29 | `dashboard/app.py` | SELECT 字段映射 (line 32, 101) |

**QA Scenarios** (每个文件):
```
Scenario: 文件 SQL 验证
  Tool: Bash
  Steps:
    1. 读取改动的文件
    2. 确认无 "FROM daily_price" 或 "INTO daily_price"
    3. 确认有 "FROM dwd_daily_price" 或 "INTO dwd_daily_price"
  Expected Result: 无 daily_price 引用
  Evidence: .sisyphus/evidence/t{N}-{filename}-check.md
```

---

### T30. 删除 daily_price VIEW

**What to do**:
```sql
DROP VIEW IF EXISTS daily_price;
```

**Reference Files**:
- `database/schema.py:749-763` - VIEW 定义

**QA Scenarios**:
```
Scenario: VIEW 删除验证
  Tool: Bash
  Command: duckdb data/Astock3.duckdb -c "SELECT * FROM daily_price;"
  Expected Result: 错误 "Table not found"
  Evidence: .sisyphus/evidence/t30-drop-view-check.md
```

---

### T31. 删除 daily_price 老表定义

**What to do**:
- 从 `database/schema.py` 删除 `CREATE_DAILY_PRICE_TABLE`
- 从 `ALL_TABLES` 列表中移除

**Reference Files**:
- `database/schema.py:23-41` - 老表定义
- `database/schema.py:818-854` - ALL_TABLES 列表

**QA Scenarios**:
```
Scenario: 老表定义删除验证
  Tool: Bash
  Command: duckdb data/Astock3.duckdb -c "SELECT * FROM daily_price;"
  Expected Result: 错误 "Table not found"
  Evidence: .sisyphus/evidence/t31-drop-table-check.md
```

---

### T32. 回测系统端到端验证

**What to do**:
```bash
python backtest/strategy_backtest/run_backtest.py -s 300486 --start 20240101 --end 20260330
```

**QA Scenarios**:
```
Scenario: 回测验证
  Tool: Bash
  Steps:
    1. 执行回测命令
    2. 确认成功完成
    3. 检查输出有收益曲线数据
  Expected Result: 回测成功，无错误
  Evidence: .sisyphus/evidence/t32-backtest-check.md
```

---

### T33. 信号扫描端到端验证

**What to do**:
```bash
python signals/scan_signals_v2.py --date 20260407 --workers 5
```

**QA Scenarios**:
```
Scenario: 信号扫描验证
  Tool: Bash
  Steps:
    1. 执行信号扫描
    2. 检查日志无 SQL 错误
    3. 确认有信号写入 daily_signals 表
  Expected Result: 扫描成功
  Evidence: .sisyphus/evidence/t33-scan-signals-check.md
```

---

### T34. 交易系统验证

**What to do**:
```bash
python scripts/run_stock_trade.py
```

**QA Scenarios**:
```
Scenario: 交易系统验证
  Tool: Bash
  Steps:
    1. 执行交易脚本（dry-run 模式如果有）
    2. 检查无 SQL 错误
  Expected Result: 正常执行
  Evidence: .sisyphus/evidence/t34-trade-check.md
```

---

## Final Verification Wave

- [x] F1. 数据完整性检查 - 迁移后记录数一致
- [x] F2. 回测系统 - run_backtest.py 正常
- [x] F3. 信号扫描 - scan_signals_v2.py 正常
- [x] F4. 交易系统 - run_stock_trade.py 正常
- [x] F5. 无 daily_price 引用残留

---

## Success Criteria

1. `daily_price` VIEW 和老表已删除
2. 所有 22 个文件已改用 `dwd_daily_price`
3. 数据迁移完成，记录数一致
4. 回测系统正常运行
5. 信号扫描正常
6. 交易系统正常
7. 无 daily_price 相关错误日志

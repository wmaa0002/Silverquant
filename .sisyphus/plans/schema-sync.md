# Plan: 更新 schema.py 以匹配 Astock3.duckdb 实际表结构

## TL;DR
根据 `data/Astock3.duckdb` 数据库中实际存在的表，更新 `database/schema.py` 文件：
- 添加 4 个缺失的表定义
- 移除冗余的 DEPRECATED 注释
- 更新 ALL_TABLES 列表

## Context

### 问题分析
通过对比 `schema.py` 和 `Astock3.duckdb` 实际表结构，发现：

| 类别 | 数量 | 说明 |
|------|------|------|
| DB有但schema缺失 | 4个 | 需要添加定义 |
| schema有但DB不存在 | 0个 | 无需删除 |
| VIEW 已正确定义 | 1个 | daily_basic |

### 数据库实际表列表 (36个)
```
agent_analysis_results      # ❌ schema缺失
backtest_daily_pnl          # ✅
backtest_performance        # ✅
backtest_run                # ✅
backtest_trades             # ✅
daily_basic                 # ✅ VIEW (已有)
daily_signals               # ✅
data_pipeline_run           # ✅
dwd_adj_factor              # ✅
dwd_balancesheet            # ✅
dwd_cashflow                # ✅
dwd_daily_basic             # ✅
dwd_daily_price             # ✅
dwd_daily_price_hfq         # ✅
dwd_daily_price_qfq         # ✅
dwd_income                  # ✅
dwd_index_daily             # ✅
dwd_stock_info              # ✅
dwd_trade_calendar          # ✅
factor_data                 # ✅
factor_ic                   # ✅
factor_return               # ✅
index_daily                 # ✅
index_info                  # ✅
industry_classification     # ✅
market_cap_group            # ✅
minute_price                # ✅ (DEPRECATED)
pipeline_monitor_flag       # ❌ schema缺失
portfolio_daily             # ✅
portfolio_daily_strategy     # ❌ schema缺失
positions                   # ✅
step_update_log             # ✅
stock_info                  # ✅ (DEPRECATED, 用dwd_stock_info)
strategies                  # ✅
trade_audit_log             # ❌ schema缺失
```

## Work Objectives

### 1. 添加缺失的表定义 (4个)

#### agent_analysis_results
```sql
CREATE TABLE IF NOT EXISTS agent_analysis_results (
    run_id VARCHAR,
    symbol VARCHAR,
    trade_date VARCHAR,
    result_json VARCHAR,
    created_at TIMESTAMP
);
```

#### pipeline_monitor_flag
```sql
CREATE TABLE IF NOT EXISTS pipeline_monitor_flag (
    id INTEGER,
    date VARCHAR,
    completed BOOLEAN,
    completed_at TIMESTAMP
);
```

#### trade_audit_log
```sql
CREATE TABLE IF NOT EXISTS trade_audit_log (
    id INTEGER,
    audit_date DATE,
    check_item VARCHAR,
    check_type VARCHAR,
    severity VARCHAR,
    status VARCHAR,
    detail VARCHAR,
    fix_action VARCHAR,
    before_val VARCHAR,
    after_val VARCHAR,
    auditor VARCHAR,
    created_at TIMESTAMP
);
```

#### portfolio_daily_strategy
```sql
CREATE TABLE IF NOT EXISTS portfolio_daily_strategy (
    id INTEGER,
    date DATE,
    strategy VARCHAR,
    position_cost DECIMAL(12,2),
    position_value DECIMAL(12,2),
    position_pnl DECIMAL(12,2),
    closed_pnl DECIMAL(12,2),
    total_pnl DECIMAL(12,2),
    trade_count INTEGER,
    notes VARCHAR,
    created_at TIMESTAMP
);
```

### 2. 清理冗余注释
- 移除 "DEPRECATED: Use dwd_xxx table instead" 注释（保留功能说明）
- 清理注释中的 "(VIEW layer complete T13)" 等内部标记

### 3. 更新 ALL_TABLES 列表
将新增的4个表添加到 `ALL_TABLES` 列表

## Verification Strategy

### QA Policy
- [ ] Python语法检查：`python3 -m py_compile database/schema.py`
- [ ] 验证表结构：对比新增定义与实际DB结构是否一致

## Execution Strategy

### Wave 1: 直接更新
- 使用 Edit 工具更新 schema.py 文件

### 依赖关系
无依赖，可以直接执行

## Commit Strategy
- Commit: YES
- Message: `refactor(schema): sync with Astock3.duckdb actual tables`
- Files: `database/schema.py`

## Success Criteria
- [ ] schema.py 中包含所有36个数据库表的定义
- [ ] Python 语法检查通过
- [ ] ALL_TABLES 列表完整
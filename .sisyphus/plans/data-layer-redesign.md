# 统一数据层(DWD)重构计划

## TL;DR

> **Quick Summary**: 基于tushare构建统一的DWD(数据明细层)，统一现有双管道架构，支持日线、财务、指数、复权因子、每日指标数据的统一存储与质量校验
>
> **Deliverables**:
> - 统一的DWD Schema定义 (dwd_*表 + VIEW向后兼容)
> - Tushare数据适配层 (封装各数据接口)
> - 数据质量校验层 (完整性/唯一性/一致性校验)
> - 增量更新流水线 (基于交易日历)
> - 向后兼容层 (VIEW映射旧表名)
>
> **Estimated Effort**: Large (架构重构 + 多数据接口适配)
> **Parallel Execution**: YES - 多wave并行
> **Critical Path**: Schema设计 → Tushare适配器 → 数据校验 → 兼容层 → 集成

---

## Context

### 原始问题
现有v1版本数据模块存在以下问题:
- **双数据管道**: V4(fetcher_daily_priceV4)和V2(fetcher_daily_price_tushare_v2)分别写入不同表
- **Schema漂移**: V2的4张表未在schema.py中定义
- **数据源不一致**: baostock/akshare/tushare混合使用，数据质量不可控
- **单位转换不统一**: tushare volume×100, amount×1000的转换分散在多处

### 用户确认需求
| 需求项 | 决策 |
|--------|------|
| 数据范围 | 日线、财务三大报表、指数、复权因子、每日指标 |
| 分钟数据 | 暂不考虑 |
| 数据库 | 继续使用DuckDB |
| 更新频率 | 每日收盘后批量更新 |
| 向后兼容 | 完全兼容现有表结构 |
| 数据质量 | 需要完整性校验 |
| 历史数据 | 保留旧表，逐步迁移 |
| Tushare权限 | 已开通基础+财务权限 |
| 财务报表 | 三大报表都要(资产负债表/利润表/现金流量表) |

### Metis Review发现的问题

**关键问题 (需确认)**:
1. 指数覆盖范围: top 20还是全部指数?
2. 财务数据粒度: 季度/半年度/年度/TTM?
3. 数据质量阈值: 完整性/重复率容忍度?

**已设置的默认值**:
- 财务数据: 季度报告数据 (reported, 非TTM)
- 指数: 主要宽基指数 (沪深300/中证500/上证50/创业板/科创50/上证指数)
- 数据完整性: ≥99% (每交易日每只股票应有1条记录)
- 重复检测: 零容忍 (date, code组合唯一)

---

## Work Objectives

### 核心目标
构建以tushare为单一数据源的统一DWD数据层，消除双管道架构，实现数据质量可观测

### 具体交付物

#### 1. 统一Schema层
- [ ] `dwd_daily_price`: 统一日线数据 (OHLCV + 复权)
- [ ] `dwd_daily_basic`: 每日指标 (PE/PB/换手率/市值等)
- [ ] `dwd_adj_factor`: 复权因子
- [ ] `dwd_income`: 利润表
- [ ] `dwd_balancesheet`: 资产负债表
- [ ] `dwd_cashflow`: 现金流量表
- [ ] `dwd_index_daily`: 指数日线
- [ ] `dwd_trade_calendar`: 交易日历
- [ ] `dwd_stock_info`: 股票基础信息
- [ ] `trade_calendar_v2`: 新版交易日历 (替代从数据存在性推断)

#### 2. Tushare适配层
- [ ] Tushare API封装 (统一接口)
- [ ] 日线数据接口
- [ ] 财务数据接口 (三大报表)
- [ ] 指数数据接口
- [ ] 复权因子接口
- [ ] 每日指标接口
- [ ] 交易日历接口

#### 3. 数据质量层
- [ ] 完整性校验 (每交易日记录数==股票数)
- [ ] 唯一性校验 (无重复date+code)
- [ ] 单位转换验证 (vol>0, amount>0)
- [ ] 复权因子链校验 (adj_factor单调性)

#### 4. 向后兼容层
- [ ] `daily_price` VIEW → 指向 `dwd_daily_price`
- [ ] `daily_basic` VIEW → 指向 `dwd_daily_basic`
- [ ] `index_daily` VIEW → 指向 `dwd_index_daily`
- [ ] `stock_info` VIEW → 指向 `dwd_stock_info`
- [ ] 旧表标记为deprecated但保留数据

#### 5. 增量更新流水线
- [ ] 基于交易日历的增量更新逻辑
- [ ] 断点续传支持
- [ ] 并行下载优化

### Definition of Done

- [ ] `database/schema.py` 包含所有DWD表定义
- [ ] `data/fetchers/tushare_adapter/` 包含所有tushare接口封装
- [ ] `data/validators/` 包含数据质量校验
- [ ] `data/updaters/fetcher_dwd.py` 支持全量+增量更新
- [ ] 向后兼容VIEW创建完成
- [ ] DuckDB中可查询所有dwd_*表

### Must Have
- [ ] Schema集中管理在schema.py (不再有inline CREATE TABLE)
- [ ] 所有单位转换在fetcher层完成
- [ ] data_source列标识数据来源(tushare)
- [ ] 使用现有code_converter进行代码格式转换
- [ ] 不添加FOREIGN KEY约束 (DuckDB性能考虑)

### Must NOT Have (Guardrails)
- [ ] 不修改现有daily_price等表结构 (向后兼容)
- [ ] 不添加分钟级数据 (用户明确排除)
- [ ] 不添加其他数据源 (tushare-only)
- [ ] 不在实际存储层计算PE/PB (在查询层计算)
- [ ] 不创建不必要的索引 (按需添加)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO (数据系统项目)
- **Automated tests**: NO (数据系统不做单元测试)
- **Framework**: N/A
- **QA Policy**: Agent-Executed QA - 通过DuckDB CLI验证数据

### QA Policy
Every task MUST include agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/`.

**验证方法**: DuckDB CLI直接查询
```bash
# 完整性检查
duckdb data/Astock3.duckdb "SELECT trade_date, COUNT(*) as rows FROM dwd_daily_price GROUP BY trade_date ORDER BY trade_date DESC LIMIT 5"

# 唯一性检查
duckdb data/Astock3.duckdb "SELECT trade_date, ts_code, COUNT(*) as cnt FROM dwd_daily_price GROUP BY 1,2 HAVING cnt > 1"

# 单位转换验证
duckdb data/Astock3.duckdb "SELECT vol, amount FROM dwd_daily_price WHERE vol = 0 OR amount = 0 LIMIT 10"
```

---

## Execution Strategy

### Parallel Execution Waves

> 最大化并行吞吐，独立任务按wave组织
> 目标: 每wave 5-8个任务

```
Wave 1 (基础设施 - 可立即开始):
├── T1: Schema设计 + 更新schema.py
├── T2: 创建trade_calendar表 + 初始化数据
├── T3: 创建dwd_stock_info表 + 迁移stock_info
├── T4: 创建dwd_trade_calendar表
├── T5: Tushare适配器基础框架
└── T6: 代码格式转换工具验证

Wave 2 (核心数据管道 - T1完成后可开始):
├── T7: Tushare日线接口封装
├── T8: Tushare财务接口封装 (income/balancesheet/cashflow)
├── T9: Tushare指数接口封装
├── T10: Tushare复权因子接口
├── T11: Tushare每日指标接口
├── T12: Tushare交易日历接口
└── T13: 数据质量校验基类

Wave 3 (更新器开发 - T7-T12完成后可开始):
├── T14: fetcher_dwd.py - 统一更新器
├── T15: 增量更新逻辑
├── T16: 断点续传支持
├── T17: 并行下载优化
└── T18: 校验任务集成

Wave 4 (向后兼容 - T14完成后可开始):
├── T19: VIEW层 - daily_price映射
├── T20: VIEW层 - daily_basic映射
├── T21: VIEW层 - index_daily映射
├── T22: VIEW层 - stock_info映射
├── T23: 旧表数据迁移验证
└── T24: 向后兼容测试

Wave FINAL (验证 - 所有wave完成后):
├── F1: Plan Compliance Audit
├── F2: Code Quality Review
├── F3: Real Manual QA
└── F4: Scope Fidelity Check
```

### Dependency Matrix

| Task | Blocked By | Blocks |
|------|------------|--------|
| T1: Schema设计 | - | T2, T3, T4, T7-T13 |
| T2: trade_calendar | T1 | T14, T15 |
| T3: dwd_stock_info | T1 | T14 |
| T4: dwd_trade_calendar | T1 | T14 |
| T5: Tushare适配器框架 | - | T7-T12 |
| T6: code_converter验证 | - | T7-T12 |
| T7: 日线接口 | T1, T5 | T14, T18 |
| T8: 财务接口 | T1, T5 | T14, T18 |
| T9: 指数接口 | T1, T5 | T14, T18 |
| T10: 复权因子接口 | T1, T5 | T14, T18 |
| T11: 每日指标接口 | T1, T5 | T14, T18 |
| T12: 交易日历接口 | T1, T5 | T14 |
| T13: 校验基类 | - | T18 |
| T14: 统一更新器 | T2, T3, T4, T7-T12 | T15, T16, T19-T22 |
| T15: 增量更新 | T14 | T18 |
| T16: 断点续传 | T14 | T18 |
| T17: 并行优化 | T14 | T18 |
| T18: 校验集成 | T7-T12, T15, T16, T17 | F1-F4 |
| T19-T22: VIEW层 | T14 | T23, T24 |
| T23: 迁移验证 | T19-T22 | F1-F4 |
| T24: 兼容测试 | T19-T22 | F1-F4 |

### Agent Dispatch Summary

- **Wave 1**: T1, T2, T3, T4, T5, T6 → `deep` (架构设计)
- **Wave 2**: T7, T8, T9, T10, T11, T12, T13 → `unspecified-high` (并行适配器开发)
- **Wave 3**: T14, T15, T16, T17, T18 → `unspecified-high` (更新器开发)
- **Wave 4**: T19, T20, T21, T22, T23, T24 → `quick` (VIEW和兼容)
- **FINAL**: F1-F4 → `oracle`/`unspecified-high`

---

## TODOs

- [x] 1. **Schema设计 - 统一DWD表定义**

  **What to do**:
  - 分析现有schema.py中的表定义
  - 设计新的dwd_*表结构，包含:
    - `dwd_daily_price`: trade_date, ts_code, open, high, low, close, vol, amount, pct_chg (统一单位: vol×100, amount×1000)
    - `dwd_daily_basic`: trade_date, ts_code, close, pe_ttm, pe, ps_ttm, ps, pcf, pb, total_mv, circ_mv, amount, turn_rate
    - `dwd_adj_factor`: ts_code, trade_date, adj_factor
    - `dwd_income`: ts_code, ann_date, f_ann_date, end_date, report_type, comp_type, basic_eps, diluted_eps, total_revenue, revenue, total_profit, profit, income_tax, n_income, n_income_attr_p, total_cogs, operate_profit, invest_income, non_op_income, asset_impair_loss, netProfitWithNonRecurring
    - `dwd_balancesheet`: ts_code, ann_date, f_ann_date, end_date, report_type, comp_type, total_assets, total_liab, total_hldr_eqy_excl_min_int, hldr_eqy_excl_min_int, minority_int, total_liab_ht_holder, notes_payable, accounts_payable, advance_receipts, total_current_assets, total_non_current_assets, fixed_assets,CIP, total_current_liab, total_non_current_liab, LT_borrow, bonds_payable
    - `dwd_cashflow`: ts_code, ann_date, f_ann_date, end_date, report_type, comp_type, net_profit, fin_exp, c_fr_oper_a, c_fr_oper_a_op_ttp, c_inf_fr_oper_a, c_paid_goods_sold, c_paid_to_for_employees, c_paid_taxes, other_cash_fr_oper_a, n_cashflow_act, c_fr_oper_b, c_fr_inv_a, c_to_inv_a, c_fr_fin_a, c_to_fin_a, n_cash_in_fin_a, n_cash_in_op_b, n_cash_out_inv_b, n_cash_out_fin_b, n_cash_in_op_c, n_cash_out_inv_c, n_cash_out_fin_c, end_cash, cap_crisis_shrg
    - `dwd_index_daily`: index_code, trade_date, open, high, low, close, vol, amount, pct_change
    - `dwd_stock_info`: ts_code, symbol, name, area, industry, market, list_date, is_hs, act_name
    - `dwd_trade_calendar`: trade_date, exchange, is_open
  - 添加data_source列默认值'tushare'
  - 更新database/schema.py的ALL_TABLES列表

  **Must NOT do**:
  - 不添加FOREIGN KEY约束
  - 不修改现有表结构
  - 不在存储层计算PE/PB等衍生指标

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 架构设计需要深入理解现有schema和业务需求
  - **Skills**: []
    - No specific skills needed for schema design
  - **Skills Evaluated but Omitted**:
    - `coding-standards`: Not needed for schema design only

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2-6)
  - **Blocks**: Tasks 7-13 (所有适配器依赖schema定义)
  - **Blocked By**: None (可立即开始)

  **References**:
  - `database/schema.py` - 现有表定义，需参照其风格
  - `data/updaters/fetcher_daily_price_tushare_v2.py:202-268` - V2表的inline定义，需迁移到schema.py
  - `data/fetchers/stock_fetcher.py:436-445` - tushare单位转换规则

  **Acceptance Criteria**:
  - [ ] `database/schema.py` 包含所有dwd_*表CREATE TABLE语句
  - [ ] ALL_TABLES列表更新
  - [ ] `duckdb data/Astock3.duckdb "SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'dwd_%'"` 返回9个表

  **QA Scenarios**:

  ```
  Scenario: Schema完整性验证
    Tool: Bash
    Preconditions: 数据库Astock3.duckdb存在
    Steps:
      1. duckdb data/Astock3.duckdb "SELECT COUNT(*) as tables FROM information_schema.tables WHERE table_name LIKE 'dwd_%'"
    Expected Result: tables >= 9 (所有dwd表)
    Failure Indicators: tables < 9
    Evidence: .sisyphus/evidence/task-1-schema-complete.txt

  Scenario: 单表结构验证
    Tool: Bash
    Preconditions: dwd_daily_price表已创建
    Steps:
      1. duckdb data/Astock3.duckdb "DESCRIBE dwd_daily_price"
    Expected Result: 包含trade_date, ts_code, open, high, low, close, vol, amount, pct_chg
    Failure Indicators: 缺少必需字段
    Evidence: .sisyphus/evidence/task-1-describe-dwd_daily_price.txt
  ```

  **Commit**: YES
  - Message: `feat(schema): add unified DWD table definitions`
  - Files: `database/schema.py`
  - Pre-commit: N/A

---

- [x] 2. **交易日历表 - 创建和初始化**

  **What to do**:
  - 创建`dwd_trade_calendar`表存储交易日历
  - 从tushare trade_cal接口获取历史交易日历
  - 初始化至少2020年至今的交易日数据
  - 表结构: trade_date (DATE, PK), exchange (VARCHAR), is_open (BOOLEAN)
  - 支持查询某日期是否交易日

  **Must NOT do**:
  - 不使用weekday<5判断交易日(中国有节假日)
  - 不假设周末以外都是交易日

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要tushare接口调用和数据校验
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3-6)
  - **Blocks**: Task 14 (增量更新需要日历)
  - **Blocked By**: Task 1 (schema需先定义)

  **References**:
  - `data/updaters/fetcher_index_daily.py:54-65` - tushare trade_cal调用示例
  - `data/fetchers/stock_fetcher.py` - rate limiter使用

  **Acceptance Criteria**:
  - [ ] `dwd_trade_calendar`表创建成功
  - [ ] 包含2020-01-01至今的交易日数据
  - [ ] `SELECT is_open FROM dwd_trade_calendar WHERE trade_date = '2026-04-04'` 返回false (清明节)

  **QA Scenarios**:

  ```
  Scenario: 交易日历数据完整性
    Tool: Bash
    Preconditions: dwd_trade_calendar已初始化
    Steps:
      1. duckdb data/Astock3.duckdb "SELECT COUNT(*) FROM dwd_trade_calendar WHERE is_open = TRUE AND trade_date >= '2020-01-01'"
    Expected Result: >= 1500条交易日记录 (约6年交易日)
    Failure Indicators: count < 1500
    Evidence: .sisyphus/evidence/task-2-calendar-complete.txt

  Scenario: 节假日验证
    Tool: Bash
    Preconditions: dwd_trade_calendar已初始化
    Steps:
      1. duckdb data/Astock3.duckdb "SELECT trade_date, is_open FROM dwd_trade_calendar WHERE trade_date BETWEEN '2026-04-01' AND '2026-04-07'"
    Expected Result: 2026-04-04(清明) is_open=FALSE, 2026-04-07 is_open=TRUE
    Failure Indicators: 2026-04-04显示为交易日
    Evidence: .sisyphus/evidence/task-2-holiday-check.txt
  ```

  **Commit**: YES
  - Message: `feat(calendar): add trade calendar table and initialize data`
  - Files: `database/schema.py` (table), `data/updaters/init_calendar.py` (init script)
  - Pre-commit: N/A

---

- [x] 3. **dwd_stock_info表 - 股票基础信息**

  **What to do**:
  - 创建`dwd_stock_info`表
  - 从tushare stock_basic接口获取股票列表
  - 字段: ts_code, symbol, name, area, industry, market, list_date, is_hs, act_name
  - 支持增量更新(新增股票检测)

  **Must NOT do**:
  - 不删除已退市股票(保留历史记录)
  - 不修改现有stock_info表结构

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要tushare接口调用和数据处理
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4-6)
  - **Blocks**: Task 14 (更新器需要股票列表)
  - **Blocked By**: Task 1

  **References**:
  - `data/fetchers/stock_fetcher.py:142-164` - stock_basic调用
  - `data/updaters/fetcher_all_stockV3.py` - 现有股票列表更新逻辑

  **Acceptance Criteria**:
  - [ ] `dwd_stock_info`表创建成功
  - [ ] `SELECT COUNT(*) FROM dwd_stock_info` >= 5000 (A股总数)
  - [ ] 包含沪深京三市股票

  **QA Scenarios**:

  ```
  Scenario: 股票列表完整性
    Tool: Bash
    Preconditions: dwd_stock_info已初始化
    Steps:
      1. duckdb data/Astock3.duckdb "SELECT COUNT(*) as total, COUNT(DISTINCT market) as markets FROM dwd_stock_info"
    Expected Result: total >= 5000, markets >= 3 (SH/SZ/BJ)
    Failure Indicators: total < 5000
    Evidence: .sisyphus/evidence/task-3-stock-list-complete.txt

  Scenario: 新股检测
    Tool: Bash
    Preconditions: dwd_stock_info包含数据
    Steps:
      1. duckdb data/Astock3.duckdb "SELECT ts_code, name, list_date FROM dwd_stock_info WHERE list_date >= '2026-01-01'"
    Expected Result: 显示2026年新上市股票
    Failure Indicators: 无结果或查询错误
    Evidence: .sisyphus/evidence/task-3-new-stocks.txt
  ```

  **Commit**: YES
  - Message: `feat(stock_info): add dwd_stock_info table`
  - Files: `database/schema.py`, `data/updaters/init_stock_info.py`
  - Pre-commit: N/A

---

- [x] 4. **代码格式转换工具验证**

  **What to do**:
  - 验证现有`data/fetchers/code_converter.py`对北交所代码的处理
  - 现有逻辑: to_tushare('000001') → '000001.SZ', to_baostock('000001') → 'sz.000001'
  - 问题: 北交所(8开头)和BJ(9开头)的处理
  - 修复code_converter中对北交所的支持
  - 添加测试用例覆盖SH/SZ/BJ三种市场

  **Must NOT do**:
  - 不破坏现有SH/SZ代码转换
  - 不修改信号系统使用的代码格式

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 小范围修复和测试
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-3, 5-6)
  - **Blocks**: Tasks 7-12 (所有tushare适配器需要代码转换)
  - **Blocked By**: None

  **References**:
  - `data/fetchers/code_converter.py` - 现有代码
  - `data/updaters/fetcher_all_stockV3.py:53` - 现有baostock代码处理bug

  **Acceptance Criteria**:
  - [ ] code_converter正确处理BJ市场代码(9开头)
  - [ ] to_tushore('830001') → '830001.BJ'
  - [ ] to_baostock('830001') → 'bj.830001'
  - [ ] 测试用例通过

  **QA Scenarios**:

  ```
  Scenario: 北交所代码转换验证
    Tool: Bash
    Preconditions: Python环境
    Steps:
      1. python -c "from data.fetchers.code_converter import to_tushare, from_tushare, to_baostock; print(to_tushare('830001'), from_tushare('830001.BJ'), to_baostore('830001'))"
    Expected Result: 830001.BJ 830001 bj.830001
    Failure Indicators: 输出包含None或错误格式
    Evidence: .sisyphus/evidence/task-4-code-converter.txt
  ```

  **Commit**: YES
  - Message: `fix(code_converter): add BJ market code support`
  - Files: `data/fetchers/code_converter.py`, `data/fetchers/test_code_converter.py`
  - Pre-commit: `python -m pytest data/fetchers/test_code_converter.py`

---

- [x] 5. **Tushare适配器基础框架**

  **What to do**:
  - 创建`data/fetchers/tushare_adapter/`目录结构
  - 实现基础类`TushareBaseFetcher`:
    - Token管理 (从环境变量TUSHARE_TOKEN)
    - Rate limiting (50 calls/min)
    - 重试逻辑 (exponential backoff)
    - 错误处理和日志
  - 遵循现有stock_fetcher中的tushare调用模式

  **Must NOT do**:
  - 不实现具体的数据接口(留给T7-T12)
  - 不破坏现有的multi_source_fetcher

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 基础框架设计需要理解现有tushare调用模式
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6-12)
  - **Blocks**: Tasks 7-12 (适配器继承此基类)
  - **Blocked By**: None (可立即开始)

  **References**:
  - `data/fetchers/stock_fetcher.py` - 现有tushare调用模式
  - `data/fetchers/rate_limiter.py` - rate limiter实现
  - `data/fetchers/multi_source_fetcher.py:24-146` - 重试和错误处理模式

  **Acceptance Criteria**:
  - [ ] `data/fetchers/tushare_adapter/base.py` 存在
  - [ ] `TushareBaseFetcher`类可实例化
  - [ ] Rate limiter正确工作

  **QA Scenarios**:

  ```
  Scenario: TushareBaseFetcher初始化
    Tool: Bash
    Preconditions: TUSHARE_TOKEN环境变量设置
    Steps:
      1. python -c "import os; os.environ['TUSHARE_TOKEN']='test'; from data.fetchers.tushare_adapter.base import TushareBaseFetcher; f = TushareBaseFetcher(); print('OK')"
    Expected Result: 打印OK，无异常
    Failure Indicators: ImportError或异常
    Evidence: .sisyphus/evidence/task-5-base-init.txt
  ```

  **Commit**: YES
  - Message: `feat(adapter): add TushareBaseFetcher framework`
  - Files: `data/fetchers/tushare_adapter/__init__.py`, `data/fetchers/tushare_adapter/base.py`
  - Pre-commit: N/A

---

- [x] 6. **Tushare日线接口封装**

  **What to do**:
  - 实现`TushareDailyPriceFetcher`类
  - 调用`pro.daily()`接口获取日线数据
  - 字段: ts_code, trade_date, open, high, low, close, vol, amount, pct_chg
  - 单位转换: vol×100, amount×1000
  - 支持按日期范围和股票列表查询
  - 按日期批量获取(所有股票单日数据)

  **Must NOT do**:
  - 不修改现有daily_price表结构
  - 不在存储层计算前复权(使用tushare的adj_factor)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要正确处理tushare API和数据转换
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 7-12)
  - **Blocks**: Task 14 (统一更新器需要此接口)
  - **Blocked By**: Tasks 1, 5

  **References**:
  - `data/fetchers/stock_fetcher.py:387-456` - 现有tushare日线获取
  - `data/updaters/fetcher_daily_price_tushare_v2.py:280-380` - V2版本的日线处理

  **Acceptance Criteria**:
  - [ ] `TushareDailyPriceFetcher`可获取单日全市场数据
  - [ ] `fetch_by_date('2026-04-03')`返回DataFrame
  - [ ] 单位转换正确(vol>0, amount>0)

  **QA Scenarios**:

  ```
  Scenario: 日线数据获取验证
    Tool: Bash
    Preconditions: TUSHARE_TOKEN设置，有效交易日
    Steps:
      1. python -c "from data.fetchers.tushare_adapter.daily import TushareDailyPriceFetcher; f = TushareDailyPriceFetcher(); df = f.fetch_by_date('2026-04-03'); print(len(df), df['vol'].min(), df['amount'].min())"
    Expected Result: rows > 4000, vol > 0, amount > 0
    Failure Indicators: rows < 4000 或 vol/amount = 0
    Evidence: .sisyphus/evidence/task-6-daily-fetch.txt
  ```

  **Commit**: YES
  - Message: `feat(adapter): add TushareDailyPriceFetcher`
  - Files: `data/fetchers/tushare_adapter/daily.py`
  - Pre-commit: N/A

---

- [x] 7. **Tushare财务接口封装**

  **What to do**:
  - 实现`TushareIncomeFetcher` - 利润表
  - 实现`TushareBalanceSheetFetcher` - 资产负债表
  - 实现`TushareCashFlowFetcher` - 现金流量表
  - 调用tushare pro接口: income, balancesheet, cashflow
  - 季度数据，按股票列表获取
  - 字段对照: 按schema.py定义的dwd_income/dwd_balancesheet/dwd_cashflow字段

  **Must NOT do**:
  - 不获取TTM数据(仅季度报告)
  - 不获取月报/半年报(仅年报和季报)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 财务数据字段多，需要正确映射
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5-6, 8-12)
  - **Blocks**: Task 14
  - **Blocked By**: Tasks 1, 5

  **References**:
  - tushare文档: pro.income(), pro.balancesheet(), pro.cashflow()
  - `database/schema.py` - dwd_income等表定义

  **Acceptance Criteria**:
  - [ ] `TushareIncomeFetcher.fetch_all()`返回利润表数据
  - [ ] `TushareBalanceSheetFetcher.fetch_all()`返回资产负债表数据
  - [ ] `TushareCashFlowFetcher.fetch_all()`返回现金流量表数据
  - [ ] 字段与schema定义匹配

  **QA Scenarios**:

  ```
  Scenario: 利润表数据获取
    Tool: Bash
    Preconditions: TUSHARE_TOKEN设置
    Steps:
      1. python -c "from data.fetchers.tushare_adapter.financial import TushareIncomeFetcher; f = TushareIncomeFetcher(); df = f.fetch_by_stock('600000.SH'); print(len(df.columns), 'basic_eps' in df.columns)"
    Expected Result: columns > 30, basic_eps exists
    Failure Indicators: 字段不匹配
    Evidence: .sisyphus/evidence/task-7-income-fetch.txt
  ```

  **Commit**: YES
  - Message: `feat(adapter): add financial statement fetchers`
  - Files: `data/fetchers/tushare_adapter/financial.py`
  - Pre-commit: N/A

---

- [x] 8. **Tushare指数/复权因子/每日指标/日历接口**

  **What to do**:
  - 实现`TushareIndexFetcher` - 指数日线 (调用pro.index_daily)
  - 实现`TushareAdjFactorFetcher` - 复权因子 (调用pro.adj_factor)
  - 实现`TushareDailyBasicFetcher` - 每日指标 (调用pro.daily_basic)
  - 实现`TushareTradeCalFetcher` - 交易日历 (调用pro.trade_cal)
  - 单位转换: 指数vol×100, amount×1000

  **Must NOT do**:
  - 不获取行业指数(仅宽基指数)
  - 不获取分钟级数据

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 多接口并行开发
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5-7, 9-12)
  - **Blocks**: Task 14
  - **Blocked By**: Tasks 1, 5

  **References**:
  - `data/updaters/fetcher_index_daily.py` - 现有指数获取
  - `data/updaters/fetcher_daily_price_tushare_v2.py` - 复权因子获取

  **Acceptance Criteria**:
  - [ ] `TushareIndexFetcher.fetch('000001.SH', '2026-04-03')` 返回数据
  - [ ] `TushareAdjFactorFetcher.fetch('600000.SH')` 返回复权因子
  - [ ] `TushareDailyBasicFetcher.fetch_by_date('2026-04-03')` 返回每日指标

  **QA Scenarios**:

  ```
  Scenario: 指数数据获取
    Tool: Bash
    Preconditions: TUSHARE_TOKEN设置
    Steps:
      1. python -c "from data.fetchers.tushare_adapter.index import TushareIndexFetcher; f = TushareIndexFetcher(); df = f.fetch('000001.SH', '2026-04-03'); print(df['close'].iloc[0] if len(df) > 0 else 'EMPTY')"
    Expected Result: close > 0
    Failure Indicators: EMPTY或close = 0
    Evidence: .sisyphus/evidence/task-8-index-fetch.txt
  ```

  **Commit**: YES
  - Message: `feat(adapter): add index, adj_factor, daily_basic, trade_cal fetchers`
  - Files: `data/fetchers/tushare_adapter/index.py`, `data/fetchers/tushare_adapter/adj_factor.py`, `data/fetchers/tushare_adapter/daily_basic.py`, `data/fetchers/tushare_adapter/trade_cal.py`
  - Pre-commit: N/A

---

- [x] 9. **数据质量校验基类**

  **What to do**:
  - 创建`data/validators/base.py` - 校验基类
  - 实现校验接口:
    - `validate_completeness(df, expected_count)` - 完整性校验
    - `validate_uniqueness(df, key_cols)` - 唯一性校验
    - `validate_no_nulls(df, required_cols)` - 非空校验
    - `validate_range(df, col, min_val, max_val)` - 范围校验
  - 实现`DataQualityError`异常类
  - 基类设计支持各数据类型的自定义校验

  **Must NOT do**:
  - 不在校验中修改数据(只读)
  - 不抛出可恢复的异常(记录并继续)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 校验逻辑设计
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5-8)
  - **Blocks**: Task 18 (校验任务集成)
  - **Blocked By**: None (可独立开发)

  **References**:
  - 现有无类似校验代码，需新建

  **Acceptance Criteria**:
  - [ ] `DataValidator`基类可继承
  - [ ] `CompletenessValidator`可检测缺失记录
  - [ ] `UniquenessValidator`可检测重复记录

  **QA Scenarios**:

  ```
  Scenario: 唯一性校验
    Tool: Bash
    Preconditions: Python环境
    Steps:
      1. python -c "import pandas as pd; from data.validators.base import UniquenessValidator; df = pd.DataFrame({'date':['2026-01-01','2026-01-01'], 'code':['600000','600000']}); v = UniquenessValidator(['date','code']); result = v.validate(df); print('PASS' if result['has_duplicates'] else 'FAIL')"
    Expected Result: FAIL (检测到重复)
    Failure Indicators: 未检测出重复
    Evidence: .sisyphus/evidence/task-9-uniqueness-validator.txt
  ```

  **Commit**: YES
  - Message: `feat(validator): add data quality validation base classes`
  - Files: `data/validators/__init__.py`, `data/validators/base.py`
  - Pre-commit: N/A

---

- [x] 10. **fetcher_dwd.py - 统一更新器**

  **What to do**:
  - 创建`data/updaters/fetcher_dwd.py`
  - 实现`DWDFetcher`类:
    - 整合所有Tushare适配器(T7-T12)
    - 全量更新模式 (指定开始日期)
    - 增量更新模式 (基于dwd_trade_calendar)
    - 断点续传 (记录最后成功更新的日期)
  - 命令行接口:
    - `--full`: 全量更新
    - `--date YYYYMMDD`: 指定日期更新
    - `--incremental`: 增量更新
    - `--data-type`: 指定数据类型

  **Must NOT do**:
  - 不删除旧数据(INSERT OR REPLACE)
  - 不修改现有V4/V2更新器(兼容现有系统)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 整合多个模块的复杂流水线
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 11-13 (后续任务依赖此完成)
  - **Blocked By**: Tasks 5-8

  **References**:
  - `data/updaters/fetcher_daily_priceV4.py` - 现有更新器模式
  - `data/updaters/fetcher_daily_price_tushare_v2.py` - V2更新器模式

  **Acceptance Criteria**:
  - [ ] `python fetcher_dwd.py --full --start-date 20240101` 可运行
  - [ ] `python fetcher_dwd.py --incremental` 可运行
  - [ ] 更新结果写入dwd_*表

  **QA Scenarios**:

  ```
  Scenario: 增量更新测试
    Tool: Bash
    Preconditions: dwd_trade_calendar已初始化
    Steps:
      1. python data/updaters/fetcher_dwd.py --date 20260403 --data-type daily
    Expected Result: 无报错，dwd_daily_price有新增记录
    Failure Indicators: 报错或无记录增加
    Evidence: .sisyphus/evidence/task-10-incremental-update.txt
  ```

  **Commit**: YES
  - Message: `feat(dwd): add unified fetcher_dwd.py updater`
  - Files: `data/updaters/fetcher_dwd.py`
  - Pre-commit: N/A

---

- [x] 11. **增量更新逻辑完善**

  **What to do**:
  - 实现基于交易日的增量更新
  - 从dwd_trade_calendar获取is_open=TRUE的日期
  - 检测最后更新日期，自动跳过已更新日期
  - 支持调度(无参数运行更新到最新)

  **Must NOT do**:
  - 不更新已关闭交易的日期
  - 不在周末运行不必要的更新

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要理解交易日历逻辑
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES (独立功能模块)
  - **Blocked By**: Task 10

  **References**:
  - `data/updaters/fetcher_daily_priceV4.py:214-225` - 现有增量逻辑

  **Acceptance Criteria**:
  - [ ] 无参数运行时自动获取最新交易日期
  - [ ] 跳过已更新日期
  - [ ] 日历表检查正确(节假日不更新)

  **Commit**: YES
  - Message: `feat(dwd): add incremental update logic`
  - Files: `data/updaters/fetcher_dwd.py`
  - Pre-commit: N/A

---

- [x] 12. **并行下载优化**

  **What to do**:
  - 复用fetcher_daily_priceV4.py的并行模式
  - 多进程按日期并行获取
  - 控制并发数(避免rate limit)
  - 进度显示和日志

  **Must NOT do**:
  - 不超过tushare rate limit (50/min)
  - 不开过多进程(资源控制)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 性能优化
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Blocked By**: Task 10

  **References**:
  - `data/updaters/fetcher_daily_priceV4.py:150-200` - 现有并行模式

  **Acceptance Criteria**:
  - [ ] 1000只股票全量更新时间 < 30分钟
  - [ ] Rate limit不触发429错误

  **Commit**: YES
  - Message: `feat(dwd): add parallel download optimization`
  - Files: `data/updaters/fetcher_dwd.py`
  - Pre-commit: N/A

---

- [x] 13. **VIEW层 - 向后兼容映射**

  **What to do**:
  - 创建VIEW: `daily_price` → `dwd_daily_price`
  - 创建VIEW: `daily_basic` → `dwd_daily_basic`
  - 创建VIEW: `index_daily` → `dwd_index_daily`
  - 创建VIEW: `stock_info` → `dwd_stock_info`
  - VIEW保持原有列名映射(如ts_code→code if needed)
  - 验证现有代码(query/INSERT不受影响)

  **Must NOT do**:
  - 不删除旧表的实际数据
  - 不修改现有表的列类型

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的VIEW创建
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 14-16)
  - **Blocks**: Task 17
  - **Blocked By**: Tasks 10, 11, 12

  **References**:
  - `database/schema.py` - VIEW创建语句参考

  **Acceptance Criteria**:
  - [ ] `SELECT * FROM daily_price LIMIT 1` 正常工作
  - [ ] VIEW与原表数据一致

  **QA Scenarios**:

  ```
  Scenario: VIEW查询兼容性
    Tool: Bash
    Preconditions: VIEW已创建
    Steps:
      1. duckdb data/Astock3.duckdb "SELECT COUNT(*) FROM daily_price WHERE trade_date = '2026-04-03'"
      2. duckdb data/Astock3.duckdb "SELECT COUNT(*) FROM dwd_daily_price WHERE trade_date = '2026-04-03'"
    Expected Result: 两个查询结果一致
    Failure Indicators: 结果不一致
    Evidence: .sisyphus/evidence/task-13-view-compatible.txt
  ```

  **Commit**: YES
  - Message: `feat(compat): add backward compatibility views`
  - Files: `database/schema.py` (VIEW定义)
  - Pre-commit: N/A

---

- [x] 14. **旧表数据迁移验证**

  **What to do**:
  - 验证旧表数据已正确迁移到新dwd_*表
  - 对比旧表和新表数据一致性
  - 确保VIEW返回数据完整
  - 标记旧表为deprecated (添加注释)

  **Must NOT do**:
  - 不删除旧表数据
  - 不修改旧表结构

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 验证任务
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Blocked By**: Task 13

  **References**:
  - N/A

  **Acceptance Criteria**:
  - [ ] `SELECT COUNT(*) FROM daily_price` == `SELECT COUNT(*) FROM dwd_daily_price`
  - [ ] 无数据丢失

  **QA Scenarios**:

  ```
  Scenario: 数据一致性验证
    Tool: Bash
    Preconditions: 迁移完成
    Steps:
      1. duckdb data/Astock3.duckdb "SELECT a.cnt as old, b.cnt as new FROM (SELECT COUNT(*) as cnt FROM daily_price) a, (SELECT COUNT(*) as cnt FROM dwd_daily_price) b"
    Expected Result: old == new
    Failure Indicators: 数据不一致
    Evidence: .sisyphus/evidence/task-14-migration-verify.txt
  ```

  **Commit**: YES
  - Message: `feat(verify): add migration verification`
  - Files: `database/schema.py` (注释标记)
  - Pre-commit: N/A

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns.

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run linter + verify all new files follow existing code patterns.

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Execute EVERY QA scenario from EVERY task - follow exact steps, capture evidence.

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", verify actual diff. Check "Must NOT do" compliance.

---

## Commit Strategy

- **Wave 1**: `git commit -m 'feat(dwd): add schema definitions and trade calendar'`
- **Wave 2**: `git commit -m 'feat(dwd): add tushare adapter layer'`
- **Wave 3**: `git commit -m 'feat(dwd): add unified updater with incremental update'`
- **Wave 4**: `git commit -m 'feat(dwd): add backward compatibility views'`

---

## Success Criteria

### Verification Commands
```bash
# Schema存在
duckdb data/Astock3.duckdb "SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'dwd_%'"

# 数据可查询
duckdb data/Astock3.duckdb "SELECT COUNT(*) FROM dwd_daily_price"
duckdb data/Astock3.duckdb "SELECT COUNT(*) FROM dwd_income"

# 向后兼容VIEW存在
duckdb data/Astock3.duckdb "SELECT view_name FROM information_schema.views WHERE view_name = 'daily_price'"
```

### Final Checklist
- [ ] 所有dwd_*表在schema.py中定义
- [ ] 所有tushare接口已封装
- [ ] 数据质量校验已实现
- [ ] 向后兼容VIEW已创建
- [ ] 增量更新逻辑可工作

# DWD层使用指南

DWD层（Data Warehouse Detail）是A股量化交易系统的统一数据仓库，基于Tushare API构建，所有数据最终存储在DuckDB中。

## 架构概览

```
Tushare API
     │
     ▼
┌─────────────────────────┐
│    Tushare适配器         │
│  (tushare_adapter/)     │
├─────────────────────────┤
│ TushareDailyPriceFetcher│
│ TushareDailyBasicFetcher│
│ TushareAdjFactorFetcher │
│ TushareIncomeFetcher    │
│ TushareBalanceSheetFetcher
│ TushareCashFlowFetcher  │
│ TushareIndexFetcher     │
│ TushareTradeCalFetcher  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│     DWDFetcher          │
│  (统一数据更新器)        │
│  fetcher_dwd.py         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│       DuckDB            │
│    data/Astock3.duckdb  │
├─────────────────────────┤
│   9个DWD表 + VIEW层     │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│      使用层              │
│  (回测/信号/交易/分析)   │
└─────────────────────────┘
```

## 数据表结构

### 1. dwd_daily_price (日线行情)

存储股票每日交易数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| trade_date | DATE | 交易日期 |
| ts_code | VARCHAR | 股票代码 (格式: 600000.SH) |
| open | FLOAT | 开盘价 |
| high | FLOAT | 最高价 |
| low | FLOAT | 最低价 |
| close | FLOAT | 收盘价 |
| vol | BIGINT | 成交量 (手) |
| amount | DOUBLE | 成交额 (元) |
| pct_chg | DOUBLE | 涨跌幅 (%) |
| data_source | VARCHAR | 数据来源，默认tushare |

**注意**: vol和amount是Tushare原始数据，vol单位为手，amount单位为元。

### 2. dwd_daily_basic (每日指标)

存储股票每日关键指标数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| trade_date | DATE | 交易日期 |
| ts_code | VARCHAR | 股票代码 |
| close | DOUBLE | 收盘价 |
| pe_ttm | DOUBLE | 市盈率(TTM) |
| pe | DOUBLE | 市盈率(静态) |
| ps_ttm | DOUBLE | 市销率(TTM) |
| ps | DOUBLE | 市销率(静态) |
| pcf | DOUBLE | 市现率 |
| pb | DOUBLE | 市净率 |
| total_mv | DOUBLE | 总市值 (元) |
| circ_mv | DOUBLE | 流通市值 (元) |
| amount | DOUBLE | 成交额 (元) |
| turn_rate | DOUBLE | 换手率 (%) |
| data_source | VARCHAR | 数据来源 |

### 3. dwd_adj_factor (复权因子)

存储复权因子数据，用于计算前复权/后复权价格。

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | VARCHAR | 股票代码 |
| trade_date | DATE | 交易日期 |
| adj_factor | DOUBLE | 复权因子 |
| data_source | VARCHAR | 数据来源 |

**复权因子用法**:
- **前复权价格** = 当前价格 × 复权因子
- **后复权价格** = 当前价格 ÷ 复权因子
- 复权因子通常在股票发生分红、送股等事件时变化

### 4. dwd_income (利润表)

存储上市公司利润表数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | VARCHAR | 股票代码 |
| ann_date | DATE | 公告日期 |
| f_ann_date | DATE | 实际公告日期 |
| end_date | DATE | 报告期末日期 |
| report_type | VARCHAR | 报告类型 (1-一季度, 2-半年度, 3-三季度, 4-年度) |
| comp_type | VARCHAR | 公司类型 |
| basic_eps | DOUBLE | 基本每股收益 |
| diluted_eps | DOUBLE | 稀释每股收益 |
| total_revenue | DOUBLE | 营业总收入 |
| revenue | DOUBLE | 营业收入 |
| total_profit | DOUBLE | 利润总额 |
| profit | DOUBLE | 净利润 |
| income_tax | DOUBLE | 所得税 |
| n_income | DOUBLE | 归属母公司净利润 |
| n_income_attr_p | DOUBLE | 归属母公司净利润 |
| total_cogs | DOUBLE | 营业成本 |
| operate_profit | DOUBLE | 营业利润 |
| invest_income | DOUBLE | 投资收益 |
| non_op_income | DOUBLE | 营业外收入 |
| asset_impair_loss | DOUBLE | 资产减值损失 |
| net_profit_with_non_recurring | DOUBLE | 非经常性损益后的净利润 |
| data_source | VARCHAR | 数据来源 |

### 5. dwd_balancesheet (资产负债表)

存储上市公司资产负债表数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | VARCHAR | 股票代码 |
| ann_date | DATE | 公告日期 |
| f_ann_date | DATE | 实际公告日期 |
| end_date | DATE | 报告期末日期 |
| report_type | VARCHAR | 报告类型 |
| comp_type | VARCHAR | 公司类型 |
| total_assets | DOUBLE | 资产总计 |
| total_liab | DOUBLE | 负债合计 |
| total_hldr_eqy_excl_min_int | DOUBLE | 股东权益合计(不含少数股东权益) |
| hldr_eqy_excl_min_int | DOUBLE | 归属母公司股东权益 |
| minority_int | DOUBLE | 少数股东权益 |
| total_liab_ht_holder | DOUBLE | 负债合计(含少数股东权益) |
| notes_payable | DOUBLE | 应付票据 |
| accounts_payable | DOUBLE | 应付账款 |
| advance_receipts | DOUBLE | 预收款项 |
| total_current_assets | DOUBLE | 流动资产合计 |
| total_non_current_assets | DOUBLE | 非流动资产合计 |
| fixed_assets | DOUBLE | 固定资产 |
| cip | DOUBLE | 在建工程 |
| total_current_liab | DOUBLE | 流动负债合计 |
| total_non_current_liab | DOUBLE | 非流动负债合计 |
| lt_borrow | DOUBLE | 长期借款 |
| bonds_payable | DOUBLE | 应付债券 |
| data_source | VARCHAR | 数据来源 |

### 6. dwd_cashflow (现金流量表)

存储上市公司现金流量表数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | VARCHAR | 股票代码 |
| ann_date | DATE | 公告日期 |
| f_ann_date | DATE | 实际公告日期 |
| end_date | DATE | 报告期末日期 |
| report_type | VARCHAR | 报告类型 |
| comp_type | VARCHAR | 公司类型 |
| net_profit | DOUBLE | 净利润 |
| fin_exp | DOUBLE | 财务费用 |
| c_fr_oper_a | DOUBLE | 经营活动现金流量净额 |
| c_fr_oper_a_op_ttp | DOUBLE | 经营活动现金净流量 |
| c_inf_fr_oper_a | DOUBLE | 经营活动现金流入小计 |
| c_paid_goods_sold | DOUBLE | 购买商品接受劳务支付的现金 |
| c_paid_to_for_employees | DOUBLE | 支付给职工以及为职工支付的现金 |
| c_paid_taxes | DOUBLE | 支付的各项税费 |
| other_cash_fr_oper_a | DOUBLE | 支付其他与经营活动有关的现金 |
| n_cashflow_act | DOUBLE | 经营活动产生的现金流量净额 |
| c_fr_oper_b | DOUBLE | 经营活动现金流量净额(间接法) |
| c_fr_inv_a | DOUBLE | 投资活动现金流入小计 |
| c_to_inv_a | DOUBLE | 投资活动现金流出小计 |
| c_fr_fin_a | DOUBLE | 筹资活动现金流入小计 |
| c_to_fin_a | DOUBLE | 筹资活动现金流出小计 |
| n_cash_in_fin_a | DOUBLE | 筹资活动现金流入净额 |
| n_cash_in_op_b | DOUBLE | 筹资活动现金流入(间接法) |
| n_cash_out_inv_b | DOUBLE | 投资活动现金流出(间接法) |
| n_cash_out_fin_b | DOUBLE | 筹资活动现金流出(间接法) |
| n_cash_in_op_c | DOUBLE | 现金流入总计(间接法) |
| n_cash_out_inv_c | DOUBLE | 投资活动现金流出总计(间接法) |
| n_cash_out_fin_c | DOUBLE | 筹资活动现金流出总计(间接法) |
| end_cash | DOUBLE | 期末现金 |
| cap_crisis_shrg | DOUBLE | 资本金 |
| data_source | VARCHAR | 数据来源 |

### 7. dwd_index_daily (指数日线)

存储指数每日行情数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| index_code | VARCHAR | 指数代码 (如 000001.SH) |
| trade_date | DATE | 交易日期 |
| open | DOUBLE | 开盘点位 |
| high | DOUBLE | 最高点位 |
| low | DOUBLE | 最低点位 |
| close | DOUBLE | 收盘点位 |
| vol | BIGINT | 成交量 (手) |
| amount | DOUBLE | 成交额 (元) |
| pct_change | DOUBLE | 涨跌幅 (%) |
| data_source | VARCHAR | 数据来源 |

**默认指数列表**:
- 000001.SH (上证指数)
- 399001.SZ (深证成指)
- 399006.SZ (创业板指)
- 000300.SH (沪深300)
- 000016.SH (上证50)
- 000905.SH (中证500)
- 000852.SH (中证1000)

### 8. dwd_stock_info (股票基础信息)

存储股票基本信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | VARCHAR | Tushare股票代码 (主键, 格式: 600000.SH) |
| symbol | VARCHAR | 股票代码 (无后缀) |
| name | VARCHAR | 股票名称 |
| area | VARCHAR | 地域 |
| industry | VARCHAR | 所属行业 |
| market | VARCHAR | 市场类型 |
| list_date | DATE | 上市日期 |
| is_hs | VARCHAR | 是否沪深港通 (N/H/S) |
| act_name | VARCHAR | 实控人名称 |
| data_source | VARCHAR | 数据来源 |

### 9. dwd_trade_calendar (交易日历)

存储交易日历信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| trade_date | DATE | 交易日期 (主键) |
| exchange | VARCHAR | 交易所 (SSE/SZSE, 主键) |
| is_open | BOOLEAN | 是否交易 |

## 使用方式

### CLI命令

#### 全量更新

```bash
python data/updaters/fetcher_dwd.py --full --data-type all
```

#### 增量更新

```bash
# 增量更新日线数据
python data/updaters/fetcher_dwd.py --incremental --data-type daily

# 增量更新所有数据
python data/updaters/fetcher_dwd.py --incremental --data-type all
```

#### 更新指定日期

```bash
# 更新单日数据
python data/updaters/fetcher_dwd.py --date 20260406 --data-type daily

# 更新日期范围
python data/updaters/fetcher_dwd.py --start-date 20260301 --end-date 20260406 --data-type daily
```

#### 并行更新

```bash
python data/updaters/fetcher_dwd.py --start-date 20260301 --end-date 20260406 --data-type daily --parallel --workers 4
```

#### 更新特定数据类型

```bash
# 日线数据
python data/updaters/fetcher_dwd.py --data-type daily --start-date 20260301 --end-date 20260406

# 每日指标
python data/updaters/fetcher_dwd.py --data-type daily_basic --start-date 20260301 --end-date 20260406

# 复权因子
python data/updaters/fetcher_dwd.py --data-type adj_factor --start-date 20200101 --end-date 20260406

# 指数日线
python data/updaters/fetcher_dwd.py --data-type index --index-code 000001.SH --start-date 20260301 --end-date 20260406

# 股票信息
python data/updaters/fetcher_dwd.py --data-type stock_info

# 交易日历
python data/updaters/fetcher_dwd.py --data-type trade_calendar --start-date 20200101 --end-date 20260406

# 财务数据 (利润表/资产负债表/现金流量表)
python data/updaters/fetcher_dwd.py --data-type financial --workers 4

# 单只股票财务数据
python data/updaters/fetcher_dwd.py --data-type income --ts-code 600000.SH
python data/updaters/fetcher_dwd.py --data-type balancesheet --ts-code 600000.SH
python data/updaters/fetcher_dwd.py --data-type cashflow --ts-code 600000.SH
```

### Python API

```python
from data.updaters.fetcher_dwd import DWDFetcher

# 初始化
fetcher = DWDFetcher()

# 更新单日日线数据
result = fetcher.update_daily('20260403', '20260403')

# 增量更新日线
result = fetcher.update_incremental('daily')

# 全量更新日线
result = fetcher.update_daily('20260101', '20260406')

# 并行更新日线
result = fetcher.update_daily_parallel('20260301', '20260406', num_workers=4)

# 更新每日指标
result = fetcher.update_daily_basic('20260301', '20260406')

# 更新复权因子
result = fetcher.update_adj_factor('20200101', '20260406')

# 更新指数日线
result = fetcher.update_index('000001.SH', '20260301', '20260406')

# 更新股票信息
result = fetcher.update_stock_info()

# 更新交易日历
result = fetcher.update_trade_calendar('20200101', '20260406')

# 多进程更新财务数据
result = fetcher.update_financial_multiprocess(num_workers=4)

# 获取表最新日期
latest = fetcher.get_latest_trade_date('dwd_daily_price')
print(f"日线最新日期: {latest}")

# 获取下一个交易日
next_date = fetcher.get_next_trade_date('20260406')
print(f"下一个交易日: {next_date}")
```

### DuckDB SQL查询

```sql
-- 查询日线数据
SELECT * FROM dwd_daily_price 
WHERE trade_date BETWEEN '2026-03-01' AND '2026-04-06'
ORDER BY trade_date DESC;

-- 查询特定股票日线
SELECT * FROM dwd_daily_price 
WHERE ts_code = '600000.SH' 
AND trade_date >= '2026-01-01'
ORDER BY trade_date;

-- 查询每日指标
SELECT d.*, b.pe_ttm, b.pb, b.turn_rate
FROM dwd_daily_price d
JOIN dwd_daily_basic b 
ON d.trade_date = b.trade_date AND d.ts_code = b.ts_code
WHERE d.ts_code = '600000.SH'
AND d.trade_date >= '2026-01-01';

-- 查询指数数据
SELECT * FROM dwd_index_daily 
WHERE index_code = '000001.SH'
AND trade_date >= '2026-03-01'
ORDER BY trade_date;

-- 查询股票基本信息
SELECT * FROM dwd_stock_info WHERE ts_code = '600000.SH';

-- 查询交易日历 (获取最近交易日)
SELECT trade_date FROM dwd_trade_calendar 
WHERE is_open = TRUE 
AND trade_date <= CURRENT_DATE
ORDER BY trade_date DESC
LIMIT 1;

-- 查询财务数据 (利润表)
SELECT * FROM dwd_income 
WHERE ts_code = '600000.SH'
AND end_date >= '2025-01-01'
ORDER BY end_date DESC;

-- 计算前复权价格
SELECT d.trade_date, d.close,
       d.close * a.adj_factor AS adj_close
FROM dwd_daily_price d
JOIN dwd_adj_factor a 
ON d.ts_code = a.ts_code AND d.trade_date = a.trade_date
WHERE d.ts_code = '600000.SH'
ORDER BY d.trade_date;
```

## 数据更新流程

### 首次全量初始化

```bash
# 1. 更新交易日历 (确定可交易的日期范围)
python data/updaters/fetcher_dwd.py --data-type trade_calendar --start-date 20200101 --end-date 20261231

# 2. 更新股票信息 (获取所有上市股票列表)
python data/updaters/fetcher_dwd.py --data-type stock_info

# 3. 更新日线数据 (建议分批，每批1-2个月)
python data/updaters/fetcher_dwd.py --data-type daily --start-date 20240101 --end-date 20240630 --parallel
python data/updaters/fetcher_dwd.py --data-type daily --start-date 20240701 --end-date 20241231 --parallel
python data/updaters/fetcher_dwd.py --data-type daily --start-date 20260101 --end-date 20260406 --parallel

# 4. 更新每日指标
python data/updaters/fetcher_dwd.py --data-type daily_basic --start-date 20240101 --end-date 20260406 --parallel

# 5. 更新复权因子
python data/updaters/fetcher_dwd.py --data-type adj_factor --start-date 20200101 --end-date 20260406

# 6. 更新指数日线
python data/updaters/fetcher_dwd.py --data-type index --index-code 000001.SH --start-date 20240101 --end-date 20260406
python data/updaters/fetcher_dwd.py --data-type index --index-code 399001.SZ --start-date 20240101 --end-date 20260406
# ... 其他指数

# 7. 更新财务数据 (可选，按需更新)
python data/updaters/fetcher_dwd.py --data-type financial --workers 4
```

### 日常增量更新

```bash
# 方式1: 使用--incremental自动判断需要更新的日期
python data/updaters/fetcher_dwd.py --incremental --data-type all

# 方式2: 手动指定日期
python data/updaters/fetcher_dwd.py --date 20260407 --data-type daily
python data/updaters/fetcher_dwd.py --date 20260407 --data-type daily_basic
```

### 完整命令示例

```bash
# 全量更新所有数据
python data/updaters/fetcher_dwd.py --full --data-type all --workers 4

# 更新单个数据类型
python data/updaters/fetcher_dwd.py --full --data-type daily --parallel --workers 4
```

## 重要注意事项

### Tushare API限制

- **标准版限制**: 50次/分钟
- 并行进程数建议不超过4个，避免触发限流
- 内部已集成`rate_limiter`进行调用频率控制

### 数据单位转换

Tushare原始数据单位与实际需要可能不同:

| 字段 | Tushare原始单位 | 存储单位 | 转换说明 |
|------|-----------------|----------|----------|
| vol (成交量) | 手 | 手 | 无需转换，已是正确单位 |
| amount (成交额) | 千元 | 元 | 需要 × 1000 |
| total_mv (总市值) | 万元 | 元 | 需要 × 10000 |
| circ_mv (流通市值) | 万元 | 元 | 需要 × 10000 |

**代码中的转换**:
```python
# 在tushare_adapter中已完成转换
df['amount'] = df['amount'] * 1000      # 千元 -> 元
df['total_mv'] = df['total_mv'] * 10000  # 万元 -> 元
df['circ_mv'] = df['circ_mv'] * 10000    # 万元 -> 元
```

### 复权因子使用

复权因子用于计算复权价格:

```sql
-- 前复权价格计算 (推荐用于技术分析)
-- 前复权价格 = 当日收盘价 × 最新复权因子
SELECT 
    d.trade_date,
    d.close AS current_price,
    d.close * a.adj_factor AS forward_adj_price
FROM dwd_daily_price d
LEFT JOIN dwd_adj_factor a 
    ON d.ts_code = a.ts_code 
    AND d.trade_date = a.trade_date
WHERE d.ts_code = '600000.SH'
ORDER BY d.trade_date;

-- 或者使用最新复权因子
WITH latest_adj AS (
    SELECT ts_code, adj_factor 
    FROM dwd_adj_factor 
    WHERE ts_code = '600000.SH'
    ORDER BY trade_date DESC 
    LIMIT 1
)
SELECT 
    d.trade_date,
    d.close * la.adj_factor AS forward_adj_price
FROM dwd_daily_price d
CROSS JOIN latest_adj la
WHERE d.ts_code = '600000.SH'
ORDER BY d.trade_date;
```

### 数据源标识

所有DWD表都有`data_source`字段标识数据来源:

- `tushare`: Tushare API获取
- 其他: 扩展预留

## 故障排查

### 常见问题

**1. Tushare API调用失败 (限流)**

```
错误: tushare rate limit exceeded
解决: 减少并行进程数，等待1分钟后重试
```

**2. 数据库连接失败**

```
错误: duckdb.IOException: Cannot open database
解决: 检查数据库文件路径是否正确，确保有写权限
```

**3. 数据为空**

```
警告: 获取到的数据为空
可能原因:
- 非交易日 (周末/节假日)
- 股票退市或停牌
- 日期范围错误 (未来日期)
解决: 确认日期为交易日，检查股票状态
```

**4. 财务数据缺失**

```
说明: 财务数据是季度更新，滞后约2周
季度报告日期: 4月底(年报)、8月底(中报)、10月底(三季报)
```

### 查看更新日志

```bash
# 查看DWD更新日志
tail -f logs/fetcher_dwd.log

# 查看错误信息
grep "ERROR" logs/fetcher_dwd.log
```

### 验证数据完整性

```sql
-- 检查各表记录数
SELECT 'dwd_daily_price' AS table_name, COUNT(*) AS cnt FROM dwd_daily_price
UNION ALL
SELECT 'dwd_daily_basic', COUNT(*) FROM dwd_daily_basic
UNION ALL
SELECT 'dwd_adj_factor', COUNT(*) FROM dwd_adj_factor
UNION ALL
SELECT 'dwd_income', COUNT(*) FROM dwd_income
UNION ALL
SELECT 'dwd_balancesheet', COUNT(*) FROM dwd_balancesheet
UNION ALL
SELECT 'dwd_cashflow', COUNT(*) FROM dwd_cashflow
UNION ALL
SELECT 'dwd_index_daily', COUNT(*) FROM dwd_index_daily
UNION ALL
SELECT 'dwd_stock_info', COUNT(*) FROM dwd_stock_info
UNION ALL
SELECT 'dwd_trade_calendar', COUNT(*) FROM dwd_trade_calendar;

-- 检查最新日期
SELECT 'dwd_daily_price' AS table_name, MAX(trade_date) AS latest FROM dwd_daily_price
UNION ALL
SELECT 'dwd_daily_basic', MAX(trade_date) FROM dwd_daily_basic
UNION ALL
SELECT 'dwd_index_daily', MAX(trade_date) FROM dwd_index_daily;

-- 检查重复数据
SELECT ts_code, trade_date, COUNT(*) AS cnt
FROM dwd_daily_price
GROUP BY ts_code, trade_date
HAVING COUNT(*) > 1;
```

### 数据源切换

如遇到Tushare API不可用，可以切换到备用数据源:

```python
# 切换到baostock (备用数据源)
# 编辑 config/settings.py
DATA_SOURCE_PRIORITY = ['baostock', 'akshare']
```

注意: 备用数据源可能数据完整性不如Tushare，建议优先使用Tushare。

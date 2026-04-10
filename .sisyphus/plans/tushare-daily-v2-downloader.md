# Tushare 日线数据下载器 V2 计划

## TL;DR

> **目标**: 创建新脚本 `fetcher_daily_price_tushare_v2.py`
> **功能**: 支持日期范围下载，使用 `pro.daily` + `pro.adj_factor` 接口
> **存储**: `Astock3.duckdb` 数据库

## 需求分析

### 数据获取方式

| 接口 | 说明 | API调用 |
|------|------|---------|
| `pro.daily(trade_date='yyyymmdd')` | 获取指定日期所有股票未复权日线数据 | 1次 |
| `pro.adj_factor(trade_date='yyyymmdd')` | 获取指定日期所有股票复权因子 | 1次 |

### 每日数据量

- 股票数量：~5000只
- API限制：每分钟最多调用50次（标准pro版）

### 日期范围下载

例如：2001-01-01 到 2026-03-01
- 总天数：~6000天
- API调用：6000 × 2 = **12000次**
- 预计耗时：12000 ÷ 50 = **240分钟 ≈ 4小时**

## 数据库表设计

### 1. daily_price_raw（新增）

存储**未复权**日线数据

```sql
CREATE TABLE IF NOT EXISTS daily_price_raw (
    trade_date DATE,
    ts_code VARCHAR,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    pre_close FLOAT,
    change FLOAT,
    pct_chg FLOAT,
    vol BIGINT,
    amount FLOAT,
    PRIMARY KEY (trade_date, ts_code)
);
```

### 2. adj_factor_tushare（新增）

存储每日复权因子

```sql
CREATE TABLE IF NOT EXISTS adj_factor_tushare (
    trade_date DATE,
    ts_code VARCHAR,
    adj_factor FLOAT,
    PRIMARY KEY (trade_date, ts_code)
);
```

### 3. daily_price_qfq（新增，计算后）

基于 `daily_price_raw` 和 `adj_factor_tushare` 计算前复权数据

```sql
CREATE TABLE IF NOT EXISTS daily_price_qfq (
    trade_date DATE,
    ts_code VARCHAR,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    vol BIGINT,
    amount FLOAT,
    adj_factor FLOAT,
    PRIMARY KEY (trade_date, ts_code)
);
```

**说明**：
- `daily_price_raw`：原始未复权数据，直接从 `pro.daily` 获取
- `adj_factor_tushare`：复权因子，从 `pro.adj_factor` 获取
- `daily_price_qfq`：前复权计算后的数据，需要根据复权因子计算

## 实现方案

### 核心逻辑

```python
def download_date_range(start_date, end_date):
    """下载日期范围内的所有数据"""
    
    # 1. 获取日期范围内的所有交易日
    trade_dates = get_trade_dates(start_date, end_date)
    
    # 2. 逐日下载
    for trade_date in trade_dates:
        # 2.1 获取当日未复权日线数据
        df_daily = ts.pro.daily(trade_date=trade_date)
        
        # 2.2 获取当日复权因子
        df_adj = ts.pro.adj_factor(trade_date=trade_date)
        
        # 2.3 计算前复权价格
        df = calculate_qfq(df_daily, df_adj)
        
        # 2.4 存储到数据库
        save_to_db(df, 'daily_price')
        save_to_db(df_adj, 'adj_factor_tushare')
```

### API限速处理

```python
from data.fetchers.rate_limiter import tushare_limiter

for trade_date in trade_dates:
    tushare_limiter.acquire()  # 获取令牌
    df_daily = ts.pro.daily(trade_date=trade_date)
    
    tushare_limiter.acquire()  # 等待下一个令牌
    df_adj = ts.pro.adj_factor(trade_date=trade_date)
```

### 断点续传

```python
# 检查数据库中已有的最新日期
existing_max_date = db.execute("SELECT MAX(trade_date) FROM adj_factor_tushare").fetchone()[0]

if existing_max_date:
    start_date = existing_max_date + 1  # 从下一个日期继续
```

## 文件结构

```
data/updaters/
├── fetcher_daily_price_tushare.py      # V1版本（当前）
└── fetcher_daily_price_tushare_v2.py   # V2版本（新创建）
```

## 实现任务

### T1: 创建脚本框架

- 文件头注释
- import语句
- 数据库连接
- 日志配置

### T2: 实现 `get_trade_dates(start_date, end_date)`

- 使用 `ts.pro.trade_cal()` 获取交易日历
- 返回日期列表

### T3: 实现 `fetch_daily_and_adj_factor(trade_date)`

- 调用 `pro.daily(trade_date)`
- 调用 `pro.adj_factor(trade_date)`
- 返回两个DataFrame

### T4: 实现 `calculate_qfq(df_daily, df_adj)`

- 合并数据
- 计算前复权价格：`qfq_price = raw_price × adj_factor`
- 返回前复权价格DataFrame

### T5: 实现数据库存储

- `save_daily_price_raw(df, db_path)` - 存储未复权数据到 `daily_price_raw`
- `save_adj_factor(df_adj, db_path)` - 存储复权因子到 `adj_factor_tushare`
- `save_daily_price_qfq(df, db_path)` - 存储前复权数据到 `daily_price_qfq`

### T6: 实现断点续传

- 检查已有数据
- 确定起始日期

### T7: 实现CLI入口

- `--start`: 起始日期
- `--end`: 结束日期
- `--db`: 数据库路径
- `--resume`: 断点续传

### T8: 测试

- 单日下载测试
- 日期范围下载测试

## 验证方法

```bash
# 下载单日数据
python data/updaters/fetcher_daily_price_tushare_v2.py --date 20260301

# 下载日期范围（最近5天）
python data/updaters/fetcher_daily_price_tushare_v2.py --start 20260301 --end 20260305

# 断点续传
python data/updaters/fetcher_daily_price_tushare_v2.py --start 20010101 --end 20260301 --resume
```

## 注意事项

1. **API限速**：tushare标准版每分钟50次调用
2. **数据量**：约5000只股票/天，需要合理安排时间
3. **复权因子**：每只股票每日一个因子
4. **断点续传**：支持中断后继续
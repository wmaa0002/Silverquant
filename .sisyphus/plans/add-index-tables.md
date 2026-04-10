# 添加指数信息表计划

## TL;DR

> 在database/schema.py中添加两个新表：index_info 和 index_daily

## TODOs

- [ ] 1. 添加 index_info 表 (指数基本信息)
- [ ] 2. 添加 index_daily 表 (指数日线行情)
- [ ] 3. 更新 ALL_TABLES 列表

## Context

根据Tushare文档:
- doc_id=94: index_basic - 指数基本信息
- doc_id=95: index_daily - 指数日线行情

## 表结构

### index_info (指数基本信息)
```sql
CREATE TABLE IF NOT EXISTS index_info (
    ts_code VARCHAR PRIMARY KEY,      -- TS指数代码
    name VARCHAR,                      -- 简称
    fullname VARCHAR,                  -- 指数全称
    market VARCHAR,                     -- 市场
    publisher VARCHAR,                   -- 发布方
    index_type VARCHAR,                 -- 指数风格
    category VARCHAR,                   -- 指数类别
    base_date VARCHAR,                 -- 基期
    base_point FLOAT,                   -- 基点
    list_date VARCHAR,                  -- 发布日期
    weight_rule VARCHAR,                -- 加权方式
    desc VARCHAR,                      -- 描述
    exp_date VARCHAR                   -- 终止日期
);
```

### index_daily (指数日线行情)
```sql
CREATE TABLE IF NOT EXISTS index_daily (
    trade_date DATE,
    ts_code VARCHAR,
    close FLOAT,                       -- 收盘点位
    open FLOAT,                         -- 开盘点位
    high FLOAT,                         -- 最高点位
    low FLOAT,                          -- 最低点位
    pre_close FLOAT,                     -- 昨日收盘点
    change_amount FLOAT,                  -- 涨跌点
    pct_chg FLOAT,                       -- 涨跌幅(%)
    vol FLOAT,                           -- 成交量(手)
    amount FLOAT,                        -- 成交额(千元)
    PRIMARY KEY (trade_date, ts_code)
);
```

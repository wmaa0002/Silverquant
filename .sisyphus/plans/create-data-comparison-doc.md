# 数据下载脚本对比文档创建计划

## TL;DR

> 在 `/Users/mawenhao/Desktop/code/股票策略/docs/数据下载脚本对比.md` 创建文档

## TODOs

- [ ] 1. 创建文档文件

## Context

需要对比两个数据下载脚本：
1. `data/updaters/fetcher_daily_price_tushare_v2.py` - Tushare Pro专用
2. `data/updaters/fetcher_daily_priceV4.py` - 多数据源通用

## 内容结构

```markdown
# 数据下载脚本对比

## 1. 脚本概述
- 数据源对比
- 下载方式对比
- 写入表格对比

## 2. 数据源
- Tushare: tushare_pro API
- MultiSourceFetcher: tushare → baostock → akshare

## 3. 写入表格
- fetcher_daily_price_tushare_v2: daily_price_raw, adj_factor_tushare, daily_price_qfq, daily_basic
- fetcher_daily_priceV4: daily_price

## 4. 下载方式
- 单进程 vs 多进程并行

## 5. 命令行参数
## 6. 使用场景
## 7. 数据流程图
```

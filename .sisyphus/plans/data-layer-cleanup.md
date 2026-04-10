# 数据层清理计划

## 背景

当前数据层存在模块冗余：
1. `stock_fetcher.py` - 混合三数据源，与adapter系列重复
2. `multi_source_fetcher.py` - 断路器封装，与fetcher_dwd.py的source切换功能重复
3. `fetcher_all_stockV3.py` / `fetcher_daily_priceV4.py` - 旧版更新脚本

### 重要架构说明

**stock_info 表 vs dwd_stock_info 表：**
- `stock_info` (legacy TABLE): `code, name, industry, market_cap, circulating_cap, listing_date, market_type, is_st, is_delisted`
- `dwd_stock_info` (DWD TABLE): `ts_code, symbol, name, area, industry, market, list_date, is_hs, act_name`
- `stock_info` (VIEW): 映射 `dwd_stock_info` 到 legacy 列名

**注意**: `fetcher_all_stockV3.py` 写入 legacy `stock_info` TABLE（有 `is_st`, `is_delisted` 等字段），而 VIEW `stock_info` 映射到 `dwd_stock_info`。两者不同！

因此清理策略调整：
- `fetcher_all_stockV3.py` **保留**（更新 legacy `stock_info` TABLE）
- 标记为 DEPRECATED 但暂不修改

---

## 引用关系分析

### 引用分析结论

**职责分离**：
- `StockFetcher`: **获取数据**（get_stock_list, get_daily_price）- `DWDFetcher`: **更新数据库**（update_stock_info, update_daily）

**可替换的引用**：
- 无（所有引用方都使用 `get_*` 方法获取数据，不是更新）

### DEPRECATED 标记（仅标记，不替换）

| 文件 | 状态 |
|------|------|
| `stock_fetcher.py` | 标记 DEPRECATED |
| `multi_source_fetcher.py` | 标记 DEPRECATED |
| `fetcher_daily_priceV4.py` | 标记 DEPRECATED |
| `fetcher_all_stockV3.py` | 保留（多进程有价值）|

---

## 实施计划

### Phase 1: 架构确认

| TODO | 描述 | 状态 |
|------|-------|------|
| 1.1 | 确认职责分离理解 | ✅ 完成 |

### Phase 2: 添加 DEPRECATED 标记

| TODO | 描述 | 状态 |
|------|-------|------|
| 2.1 | `stock_fetcher.py` | ✅ 完成 |
| 2.2 | `multi_source_fetcher.py` | ✅ 完成 |
| 2.3 | `fetcher_daily_priceV4.py` | ✅ 完成 |
| 2.4 | `fetcher_all_stockV3.py` | 待办 |

### Phase 3: 恢复误改的文件

| TODO | 描述 | 状态 |
|------|-------|------|
| 3.1 | 恢复 `data/__init__.py` | ✅ 完成 |
| 3.2 | 恢复 `update_outdated_stocks.py` | ✅ 完成 |
| 3.3 | 恢复 `force_update_daily_price.py` | ✅ 完成 |

**注意**: `init_project.py`, `test_db_integration.py`, `stock_adapter.py` 使用 `get_*` 方法获取数据，应保留 `StockFetcher`

---

## 详细改动

### 导入替换（共6处）

| 文件 | 旧导入 | 新导入 |
|------|--------|---------|
| `data/__init__.py` | `from .fetchers.stock_fetcher import StockFetcher` | `from .updaters.fetcher_dwd import DWDFetcher` |
| `scripts/data_check/update_outdated_stocks.py` | 同上 | 同上 |
| `scripts/data_check/force_update_daily_price.py` | 同上 | 同上 |
| `scripts/init_project.py` (2处) | 同上 | 同上 |
| `tests/test_db_integration.py` | 同上 | 同上 |
| `agent_integration/.../stock_adapter.py` | `StockFetcher('akshare')` | `DWDFetcher(source='akshare')` |

### DEPRECATED 标记（共4处）

| 文件 | 标记内容 |
|------|---------|
| `data/fetchers/stock_fetcher.py` | `[DEPRECATED] 请使用 fetcher_dwd.DWDFetcher` |
| `data/fetchers/multi_source_fetcher.py` | `[DEPRECATED] 请使用 fetcher_dwd.DWDFetcher` |
| `data/updaters/fetcher_daily_priceV4.py` | `[DEPRECATED] 请使用 fetcher_dwd.update_daily()` |
| `data/updaters/fetcher_all_stockV3.py` | `[DEPRECATED] 写入 legacy stock_info 表，暂保留` |

### 保留不变

- `workflow_scheduler.py` - stock_info/daily_price 步骤仍用旧脚本
- `fetcher_all_stockV3.py` - 更新 legacy `stock_info` TABLE
- `fetcher_daily_priceV4.py` - 多进程并行，仍有价值

---

## 验证清单

| 验证项 | 命令 |
|--------|------|
| DWDFetcher 导入 | `python -c "from data.updaters.fetcher_dwd import DWDFetcher; print('OK')"` |
| baostock_adapter 导入 | `python -c "from data.fetchers.baostock_adapter import BaostockDailyPriceFetcher; print('OK')"` |
| 流水线测试 | `python scripts/workflow_scheduler.py --help` |

---

## 回滚方案

```bash
git checkout HEAD~1 -- data/fetchers/stock_fetcher.py data/fetchers/multi_source_fetcher.py
```

---

## 预计改动

| 文件 | 操作 | 原因 |
|------|------|------|
| `data/__init__.py` | 导出 `DWDFetcher` | 统一入口 |
| `scripts/data_check/update_outdated_stocks.py` | 改用 `DWDFetcher` | 移除 `stock_fetcher` 依赖 |
| `scripts/data_check/force_update_daily_price.py` | 改用 `DWDFetcher` | 移除 `stock_fetcher` 依赖 |
| `scripts/init_project.py` | 改用 `DWDFetcher` | 移除 `stock_fetcher` 依赖 |
| `tests/test_db_integration.py` | 改用 `DWDFetcher` | 移除 `stock_fetcher` 依赖 |
| `agent_integration/.../stock_adapter.py` | 改用 `DWDFetcher(source='akshare')` | 移除 `stock_fetcher` 依赖 |
| `scripts/workflow_scheduler.py` | 保留旧方式 | stock_info/daily_price 步骤仍用旧脚本 |
| `data/fetchers/stock_fetcher.py` | 添加 DEPRECATED 标记 | 功能重复 |
| `data/fetchers/multi_source_fetcher.py` | 添加 DEPRECATED 标记 | 功能重复 |
| `data/updaters/fetcher_daily_priceV4.py` | 添加 DEPRECATED 标记 | 被 `fetcher_dwd` 替代 |
| `data/updaters/fetcher_all_stockV3.py` | 添加 DEPRECATED 标记 | 写入 legacy 表，暂保留 |

**总计**: 4个 DEPRECATED 标记 + 6个导入修改
**保留**: `fetcher_all_stockV3.py` 和 `fetcher_daily_priceV4.py` 暂不删除（更新不同表）


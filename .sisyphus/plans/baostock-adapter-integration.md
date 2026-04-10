# Baostock Adapter 整合计划

## 背景

当前数据层有两个数据源适配器系列：
1. **tushare_adapter** - 基于 Tushare Pro API
2. **stock_fetcher.py** - 基于 MultiSourceFetcher，支持 baostock/akshare/tushare

但 baostock 的适配逻辑散落在 `stock_fetcher.py` 中，不够模块化。需要创建独立的 `baostock_adapter` 模块，与 `tushare_adapter` 架构对齐。

---

## 1. Baostock query_history_k_data_plus 字段分析

### 返回字段

| 字段 | 类型 | 说明 | dwd_daily_price映射 |
|------|------|------|---------------------|
| `date` | str | 交易日期 (YYYY-MM-DD) | → `trade_date` |
| `code` | str | 股票代码 (sz.300486/sh.600000) | → `ts_code` (300486.SZ/600000.SH) |
| `open` | float | 开盘价 | → `open` |
| `high` | float | 最高价 | → `high` |
| `low` | float | 最低价 | → `low` |
| `close` | float | 收盘价 | → `close` |
| `preclose` | float | 前收价 | (备用) |
| `volume` | int | 成交量 (**股**，已是最终单位) | → `vol` |
| `amount` | float | 成交额 (**元**，已是最终单位) | → `amount` |
| `adjustflag` | str | 复权状态 (1=后复权,2=前复权,3=不复权) | → `data_source` 标记 |
| `turn` | float | 换手率 | → `dwd_daily_basic.turn_rate` |
| `tradestatus` | str | 交易状态 (1=正常,0=停牌) | 过滤停牌股票 |
| `pctChg` | float | 涨跌幅 (%) | → `pct_chg` |
| `isST` | str | 是否ST | 用于ST过滤 |

### 关键发现

1. **单位差异**：
   - baostock `volume` 已经是**股**（无需×100转换）
   - baostock `amount` 已经是**元**（无需×1000转换）

2. **代码格式**：
   - baostock: `sz.300486`, `sh.600000`
   - dwd_daily_price: `300486.SZ`, `600000.SH`

---

## 2. 目录结构设计

```
data/fetchers/
├── tushare_adapter/          # 已有
│   ├── __init__.py
│   ├── base.py               # TushareBaseFetcher 基类
│   ├── daily.py             # TushareDailyPriceFetcher
│   └── ...
│
├── baostock_adapter/        # 新建
│   ├── __init__.py
│   ├── base.py               # BaostockBaseFetcher 基类
│   ├── daily.py             # BaostockDailyPriceFetcher
│   ├── stock_info.py        # BaostockStockInfoFetcher
│   └── code_converter.py     # sz.300486 → 300486.SZ 转换
```

---

## 3. 模块接口设计

### BaostockBaseFetcher (base.py)

```python
class BaostockBaseFetcher:
    """
    Baostock适配器基类
    
    提供:
    - 自动登录/登出
    - session管理
    - 错误处理和重试
    """
    
    def __init__(self):
        self._ensure_login()
    
    def _convert_code(self, code: str) -> str:
        """
        转换代码格式
        - 输入: '300486' 或 'sz.300486' 或 '300486.SZ'
        - 输出: 'sz.300486' (baostock格式)
        """
```

### BaostockDailyPriceFetcher (daily.py)

```python
class BaostockDailyPriceFetcher(BaostockBaseFetcher):
    """
    Baostock日线数据获取器
    
    接口:
    - fetch_by_code(code, start_date, end_date) → DataFrame
    
    返回字段:
    - ts_code, trade_date, open, high, low, close, vol, amount, pct_chg, data_source
    """
    
    def fetch_by_code(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjustflag: str = '3'
    ) -> pd.DataFrame:
```

---

## 4. 字段转换规则

### 代码格式转换

```python
# 内部格式 → baostock格式
def convert_code_to_baostock(code: str) -> str:
    # '300486' → 'sz.300486'
    # '300486.SZ' → 'sz.300486'
    # '600000.SH' → 'sh.600000'
    
# baostock格式 → 内部格式
def convert_code_from_baostock(code: str) -> str:
    # 'sz.300486' → '300486.SZ'
    # 'sh.600000' → '600000.SH'
```

### 单位转换

**重要发现**：baostock 的 volume 和 amount **已经是最终单位**（股和元），不需要转换！

---

## 5. 实施计划

### Phase 1: 基础模块 (新建 baostock_adapter)

| TODO | 描述 | 状态 |
|------|------|------|
| T1 | 创建 `data/fetchers/baostock_adapter/` 目录 | ✅ 完成 |
| T2 | 创建 `__init__.py` 导出文件 | ✅ 完成 |
| T3 | 创建 `code_converter.py` - 代码格式转换 | ✅ 完成 |
| T4 | 创建 `base.py` - BaostockBaseFetcher 基类 | ✅ 完成 |
| T5 | 创建 `daily.py` - BaostockDailyPriceFetcher | ✅ 完成 |
| T6 | 创建 `stock_info.py` - BaostockStockInfoFetcher | ✅ 完成 |

### Phase 2: 整合到 fetcher_dwd

| TODO | 描述 | 状态 |
|------|------|------|
| T7 | 在 `fetcher_dwd.py` 中添加 source 参数 | ✅ 完成 |
| T8 | 修改 `DWDFetcher.update_daily()` 支持 baostock | ✅ 完成 |
| T9 | 添加 `DWDFetcher.update_daily_by_stock()` 方法 | ✅ 完成 |

### Phase 3: 整合到 workflow_scheduler

| TODO | 描述 | 状态 |
|------|------|------|
| T10 | 修改 `run_step_daily_price()` 支持多数据源 | ✅ 完成 |
| T11 | 更新 `STEP_DEPENDENCIES` 注释 | ✅ 完成 |

### Phase 4: 测试验证

| TODO | 描述 | 状态 |
|------|------|------|
| T12 | 测试 baostock 日线数据获取 | ✅ 完成 |
| T13 | 验证字段映射正确性 | ✅ 完成 |
| T14 | 对比 baostock vs tushare 数据一致性 | ✅ 完成 |

---

## 6. 关键文件改动

### 新建文件 (5个)

| 文件 | 描述 |
|------|------|
| `data/fetchers/baostock_adapter/__init__.py` | 模块导出 |
| `data/fetchers/baostock_adapter/base.py` | 基类 |
| `data/fetchers/baostock_adapter/daily.py` | 日线数据获取器 |
| `data/fetchers/baostock_adapter/stock_info.py` | 股票信息获取器 |
| `data/fetchers/baostock_adapter/code_converter.py` | 代码转换工具 |

### 修改文件 (3个)

| 文件 | 改动 |
|------|------|
| `data/fetchers/__init__.py` | 添加 baostock_adapter 导出 |
| `data/updaters/fetcher_dwd.py` | 添加 source 参数和 baostock 支持 |
| `scripts/workflow_scheduler.py` | 支持切换数据源 |

---

## 7. 风险与注意事项

1. **数据单位差异**：baostock 的 volume/amount 已是最终单位，**不要**乘以100/1000
2. **代码格式**：baostock 使用 `sz.XXXXXX` / `sh.XXXXXX`，需要转换
3. **API限制**：baostock 无明确调用频率限制，但应避免过度请求
4. **session管理**：baostock 需要每次操作前检查登录状态
5. **停牌股票**：baostock 返回 `tradestatus=0`，需要过滤

---

## 8. 预期产出

1. **baostock_adapter 模块**：与 tushare_adapter 架构对齐的完整适配器
2. **fetcher_dwd 增强**：支持切换 tushare/baostock 数据源
3. **workflow_scheduler 增强**：支持指定数据源执行流水线

---

*本计划基于对 baostock query_history_k_data_plus() API 的实际测试结果制定。*

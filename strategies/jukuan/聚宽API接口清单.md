# 聚宽API接口清单

> 策略文件：`小盘股动态持有策略没有空仓月份.py`

---

## 一、聚宽内置函数/类

### 1.1 策略设置

| API | 行号 | 说明 | 示例 |
|-----|------|------|------|
| `set_option` | 15,21 | 设置策略选项 | `set_option('avoid_future_data', True)` |
| `set_benchmark` | 19 | 设置基准 | `set_benchmark('399101.XSHE')` |
| `set_slippage` | 23 | 设置滑点 | `FixedSlippage(3/10000)` |
| `set_order_cost` | 25 | 设置交易成本 | `OrderCost(...)` |
| `log.set_level` | 27-29 | 设置日志级别 | `log.set_level('order', 'error')` |

### 1.2 定时任务

| API | 行号 | 说明 | 示例 |
|-----|------|------|------|
| `run_daily` | 54-57 | 每日定时任务 | `run_daily(prepare_stock_list, '9:05')` |
| `run_weekly` | 58 | 每周定时任务 | `run_weekly(weekly_adjustment, 2, '10:00')` |

### 1.3 交易函数

| API | 行号 | 说明 | 示例 |
|-----|------|------|------|
| `order_target_value` | 126,145,190,195,210,278,298 | 目标金额下单 | `order_target_value(stock, value)` |

---

## 二、数据获取函数

### 2.1 行情数据

| API | 行号 | 说明 | 示例 |
|-----|------|------|------|
| `get_price` | 68,142,200,217 | 获取行情数据 | `get_price(stock, end_date=..., frequency='daily')` |
| `get_current_data` | 232,291 | 获取当前数据 | `get_current_data()` |
| `history` | 103,234 | 获取历史数据 | `history(1, unit='1d', field='close')` |

**get_price 参数：**
```python
get_price(
    security,              # 股票代码/列表
    end_date,              # 结束日期
    count,                 # 数量
    fields,                # 字段：close/high_limit/low_limit/open
    frequency,             # 频率：daily/1m(分钟)
    panel,                 # False返回DataFrame
    fill_paused,           # 是否填充停牌
    skip_paused,           # 是否跳过停牌
    fq                      # 复权类型：pre(前复权)
)
```

### 2.2 股票列表

| API | 行号 | 说明 | 示例 |
|-----|------|------|------|
| `get_index_stocks` | 80,200 | 获取指数成分股 | `get_index_stocks('399101.XSHE')` |

### 2.3 财务数据

| API | 行号 | 说明 | 示例 |
|-----|------|------|------|
| `get_fundamentals` | 93 | 获取财务数据 | `get_fundamentals(query_obj)` |
| `finance.run_query` | 264 | 查询财务表 | `finance.run_query(query_obj)` |
| `get_security_info` | 251 | 获取证券信息 | `get_security_info(stock).start_date` |

---

## 三、查询对象 (query)

### 3.1 表字段

| 表 | 字段 | 行号 | 说明 |
|----|------|------|------|
| `valuation` | `code` | 85,87 | 股票代码 |
| `valuation` | `market_cap` | 88 | 总市值（亿元） |
| `income` | `np_parent_company_owners` | 89 | 归属于母公司净利润 |
| `income` | `net_profit` | 90 | 净利润 |
| `income` | `operating_revenue` | 91 | 营业收入 |
| `finance.STK_AUDIT_OPINION` | `code` | 262 | 股票代码 |
| `finance.STK_AUDIT_OPINION` | `report_type` | 262 | 审计意见类型 |
| `finance.STK_AUDIT_OPINION` | `pub_date` | 263 | 发布日期 |

### 3.2 查询筛选

| 方法 | 说明 | 示例 |
|------|------|------|
| `query(...)` | 创建查询对象 | `query(valuation.code, ...)` |
| `.filter(...)` | 筛选条件 | `.filter(valuation.code.in_(list))` |
| `.order_by(...)` | 排序 | `.order_by(valuation.market_cap.asc())` |
| `.limit(...)` | 限制数量 | `.limit(10)` |

### 3.3 筛选条件

| 条件 | 说明 |
|------|------|
| `valuation.code.in_(list)` | 股票代码在列表中 |
| `valuation.market_cap.between(a, b)` | 市值在范围内 |
| `income.xxx > 0` | 财务指标大于0 |
| `finance.STK_AUDIT_OPINION.pub_date >= date` | 日期筛选 |

---

## 四、Context 对象

### 4.1 账户信息

| 属性 | 行号 | 说明 |
|------|------|------|
| `context.portfolio.positions` | 65,158,273等 | 当前持仓 |
| `context.portfolio.cash` | 164,276 | 可用资金 |
| `context.previous_date` | 68,216等 | 昨日日期 |
| `context.current_dt` | 138 | 当前时间 |

### 4.2 Position 对象属性

| 属性 | 说明 |
|------|------|
| `position.price` | 当前价格 |
| `position.avg_cost` | 平均成本 |
| `position.value` | 持仓市值 |
| `position.total_amount` | 持仓数量 |

---

## 五、Current Data 对象

### 5.1 股票属性

| 属性 | 行号 | 说明 |
|------|------|------|
| `current_data[stock].paused` | 238 | 是否停牌 |
| `current_data[stock].is_st` | 240 | 是否ST |
| `current_data[stock].name` | 242 | 股票名称 |
| `current_data[stock].high_limit` | 246 | 涨停价 |
| `current_data[stock].low_limit` | 248 | 跌停价 |
| `current_data[stock].last_price` | 296 | 最新价 |

---

## 六、日志函数

| API | 行号 | 说明 |
|-----|------|------|
| `log.set_level()` | 27-29 | 设置日志级别 |
| `log.info()` | 99,107,116等 | 信息日志 |
| `log.debug()` | 191,196,208 | 调试日志 |
| `log.error()` | - | 错误日志 |

---

## 七、导入模块

```python
from jqdata import *              # 主模块
from jqfactor import *            # 因子模块
from jqdata import finance        # 财务模块
```

---

## 八、API使用统计

| 类别 | 数量 |
|------|------|
| 策略设置函数 | 5 |
| 定时任务函数 | 2 |
| 交易函数 | 1 |
| 数据获取函数 | 7 |
| 查询/筛选 | 10+ |

---

*整理时间: 2026-03-01*

# A股量化交易回测系统

## 项目简介

A股量化交易回测系统是基于Backtrader的量化交易框架，专为A股市场设计。系统支持多数据源获取、多策略信号生成、批量回测和实盘交易。

### 核心特性

- 多数据源：支持akshare、baostock、tushare自动切换
- 多策略信号：B1、B2、BLK、S1、SCB、DZ30、DL等策略
- 批量回测：支持多策略、多股票的批量回测分析
- DuckDB存储：高性能本地数据库存储
- 多进程扫描：全市场信号并行扫描
- Web仪表板：实时监控交易状态

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据层 (Data)                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   akshare    │  │   baostock   │  │   tushare    │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
│         └────────────────┼─────────────────┘                   │
│                          ▼                                      │
│              ┌──────────────────────┐                            │
│              │  MultiSourceFetcher │                            │
│              │    (CircuitBreaker)  │                            │
│              └──────────┬───────────┘                            │
│                         ▼                                        │
│         ┌────────────────────────────┐                           │
│         │  fetcher_daily_priceV4.py │                           │
│         │      (多进程下载)          │                           │
│         └──────────┬─────────────────┘                           │
│                    ▼                                             │
│              ┌─────────────┐                                     │
│              │  DuckDB     │                                     │
│              │ daily_price │                                     │
│              └──────┬──────┘                                     │
└─────────────────────┼───────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      信号层 (Signals)                             │
├─────────────────────────────────────────────────────────────────┤
│         ┌─────────────────────────────┐                          │
│         │   scan_signals_v2.py        │                          │
│         │     (多进程全市场扫描)       │                          │
│         └──────────┬──────────────────┘                          │
│                    ▼                                             │
│    ┌────────────────────────────────────────────┐                 │
│    │           信号计算模块 (singal_cal/)       │                 │
│    ├──────────┬──────────┬──────────┬─────────┤                 │
│    │basic_module│ B1      │ B2       │ S1      │                 │
│    │ MACD/KDJ  │ BLK      │ SCB      │ DZ30    │                 │
│    └──────────┴──────────┴──────────┴─────────┘                 │
│                    ▼                                             │
│              ┌─────────────┐                                     │
│              │  DuckDB     │                                     │
│              │daily_signals│                                     │
│              └─────────────┘                                     │
└─────────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      回测层 (Backtest)                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │  BacktestEngine  │    │ multi_dimension  │                   │
│  │   (backtrader)   │    │   (多维度分析)    │                   │
│  └────────┬─────────┘    └──────────────────┘                   │
│           ▼                                                      │
│  ┌─────────────────────┐  ┌─────────────────────┐                │
│  │  run_backtest.py    │  │batch_backtest_V3.py│                │
│  │    (单次回测)        │  │     (批量回测)      │                │
│  └─────────┬───────────┘  └─────────┬───────────┘                │
│            ▼                          ▼                           │
│      ┌─────────────────────────────────────────┐                   │
│      │              DuckDB                     │                   │
│      │ backtest_run / trades / performance    │                   │
│      └─────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      交易层 (Trading)                            │
├─────────────────────────────────────────────────────────────────┤
│         ┌─────────────────────────────┐                           │
│         │    run_stock_trade.py      │                           │
│         │       (主交易入口)          │                           │
│         └──────────┬────────────────┘                            │
│                    ▼                                            │
│         ┌─────────────────────┐                                   │
│         │      DuckDB         │                                   │
│         │    positions        │                                   │
│         └─────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI集成层 (agent_integration/)                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ LLM适配器   │  │   交易图    │  │  策略优化   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Web仪表板 (dashboard/)                          │
├─────────────────────────────────────────────────────────────────┤
│         ┌─────────────────────────────┐                          │
│         │      Flask Web应用          │                          │
│         │   实时监控 / 统计分析        │                          │
│         └─────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## 目录结构

```
股票策略/
├── agent_integration/          # AI Agent集成
│   ├── llm_adapter.py         # LLM适配器
│   └── trading_graph.py       # 交易图
├── backtest/                   # 回测引擎
│   ├── engine.py              # BacktestEngine封装
│   ├── multi_dimension.py     # 多维度分析
│   └── strategy_backtest/      # 策略回测
│       ├── run_backtest.py    # 单次回测入口
│       └── batch_backtest_V3.py # 批量回测
├── config/                      # 配置文件
│   └── settings.py             # 系统配置
├── dashboard/                   # Web仪表板
│   └── app.py                  # Flask应用
├── data/                        # 数据系统
│   ├── fetchers/               # 数据获取
│   │   ├── stock_fetcher.py   # 数据源适配器
│   │   └── multi_source_fetcher.py # 多数据源切换
│   └── updaters/              # 数据更新
│       ├── fetcher_daily_priceV4.py # 日线数据下载
│       ├── fetcher_all_stockV3.py   # 股票列表下载
│       └── fetcher_index_daily.py   # 指数数据下载
├── database/                    # 数据库
│   ├── db_manager.py          # CRUD操作
│   └── schema.py              # 表结构定义
├── scripts/                     # 运营脚本
│   └── run_stock_trade.py     # 主交易入口
├── signals/                     # 信号系统
│   ├── scan_signals_v2.py     # 多进程信号扫描
│   └── singal_cal/           # 信号计算模块
│       ├── __init__.py
│       ├── basic_module.py    # 技术指标计算
│       ├── B1_strategy_module.py  # B1买入策略
│       ├── B2_strategy_module.py   # B2买入策略
│       ├── S1_module.py       # S1卖出策略
│       ├── BLKB2_strategy_module.py # BLK+BLKB2策略
│       ├── SCB_strategy_module.py  # SCB策略
│       └── DZ30_strategy_module.py # DZ30策略
├── strategies/                   # 策略实现
│   └── base/
│       └── framework_strategy.py # 策略基类
├── tools/                       # 工具
├── AGENTS.md                   # Agent集成文档
├── README.md                   # 本文档
└── requirements.txt            # 依赖
```

## 快速开始

### 环境要求

- Python 3.8+
- DuckDB
- Backtrader
- akshare / baostock / tushare

### 安装依赖

```bash
pip install -r requirements.txt
```

### 基本命令

```bash
# 数据下载
python data/updaters/fetcher_daily_priceV4.py --start-date 20260330

# 指数数据下载
python data/updaters/fetcher_index_daily.py --all

# 股票列表更新
python data/updaters/fetcher_all_stockV3.py

# 信号扫描
python signals/scan_signals_v2.py --date 20260330 --workers 10

# 单次回测
python backtest/strategy_backtest/run_backtest.py -s 300486 --start 20240101

# 批量回测
python backtest/strategy_backtest/batch_backtest_V3.py -l 50

# 主交易
python scripts/run_stock_trade.py
```

## 模块详解

### 数据下载系统 (data/)

#### stock_fetcher.py

数据源适配器，统一封装akshare、baostock、tushare接口。

```python
from data.fetchers.stock_fetcher import StockFetcher

fetcher = StockFetcher(source='akshare')
df = fetcher.get_daily_price('600000', start_date='20240101')
```

#### multi_source_fetcher.py

多数据源故障切换，集成CircuitBreaker模式。主数据源失败时自动切换备用源。

```python
from data.fetchers.multi_source_fetcher import MultiSourceFetcher

fetcher = MultiSourceFetcher()
df = fetcher.get_daily_price('600000', start_date='20240101')
```

#### fetcher_daily_priceV4.py

多进程日线数据下载器，采用8→3→1进程分级策略。

```bash
# 下载指定日期之后的日线数据
python data/updaters/fetcher_daily_priceV4.py --start-date 20260330

# 指定进程数
python data/updaters/fetcher_daily_priceV4.py --start-date 20260330 --workers 10
```

#### fetcher_all_stockV3.py

全量股票列表下载更新。

```bash
python data/updaters/fetcher_all_stockV3.py
```

#### fetcher_index_daily.py

指数数据下载器，支持下载指数基本信息(index_info)和指数日线数据(index_daily)。

**主要功能：**
- 下载/更新指数基本信息（交易所代码、指数名称、发布日期、终止日期）
- 下载指数日线数据（开盘、收盘、最高、最低、成交量、成交额等）
- 支持断点续传（自动跳过已下载数据）
- 支持指定指数和日期范围

```bash
# 全量下载：指数基本信息 + 日线数据
python data/updaters/fetcher_index_daily.py --all

# 只下载指数基本信息
python data/updaters/fetcher_index_daily.py --basic

# 下载日线数据（默认断点续传）
python data/updaters/fetcher_index_daily.py --start 20260101 --end 20260401

# 下载指定指数
python data/updaters/fetcher_index_daily.py --ts_code 000001.SH --start 20260101 --end 20260401

# 禁用断点续传
python data/updaters/fetcher_index_daily.py --all --no-resume
```

**参数说明：**
| 参数 | 说明 |
|------|------|
| `--all` | 同时下载指数基本信息和日线数据 |
| `--basic` | 只下载指数基本信息 |
| `--ts_code` | 指定指数代码 (如 000001.SH, 399001.SZ) |
| `--start` | 开始日期 (YYYYMMDD) |
| `--end` | 结束日期 (YYYYMMDD) |
| `--no-resume` | 禁用断点续传 |
| `--db` | 数据库路径 |

### 信号系统 (signals/)

#### scan_signals_v2.py

多进程全市场信号扫描，支持多worker并行处理。

```bash
# 扫描指定日期信号
python signals/scan_signals_v2.py --date 20260330 --workers 10

# 指定策略扫描
python signals/scan_signals_v2.py --date 20260330 --strategy B1 --workers 10
```

#### singal_cal/basic_module.py

技术指标计算模块，提供KDJ、MACD、RSI、MA、BBI、布林线等指标。

```python
from signals.singal_cal.basic_module import BasicModule

module = BasicModule()
df_with_indicators = module.calculate_indicators(df)
```

#### B1策略 (B1_strategy_module.py)

B1买入策略，触发条件：

- KDJ_J < 13
- MACD多头排列
- 趋势线 > 多空线
- B1总分 ≥ 8

#### B2策略 (B2_strategy_module.py)

B2买入策略，触发条件：

- 前日J ≤ 21 或 RSI1 ≤ 21
- 今日放量
- 涨幅 > 3.95%

#### S1卖出策略 (S1_module.py)

S1卖出策略，规则：

- S1 ≥ 10：全卖
- S1 ≥ 5：卖半仓
- 跌破多空线：清仓

#### BLK策略 (BLKB2_strategy_module.py)

暴力K策略，触发条件：

- 涨跌幅 > 4%
- 成交量 > 参考量1.8倍

#### SCB策略 (SCB_strategy_module.py)

沙尘暴策略

#### DZ30策略 (DZ30_strategy_module.py)

单针30策略

### 回测系统 (backtest/)

#### engine.py

BacktestEngine封装backtrader，提供统一的回测接口。

```python
from backtest.engine import BacktestEngine

engine = BacktestEngine()
result = engine.run(strategy_class, stock_code, start_date, end_date)
```

#### multi_dimension.py

多维度分析，支持按行业、市值分组分析回测结果。

```python
from backtest.multi_dimension import MultiDimensionAnalyzer

analyzer = MultiDimensionAnalyzer()
result = analyzer.analyze_by_industry(backtest_id)
result = analyzer.analyze_by_market_cap(backtest_id)
```

#### run_backtest.py

单次回测入口

```bash
python backtest/strategy_backtest/run_backtest.py -s 300486 --start 20240101 --end 20260330
```

参数：

- `-s`：股票代码
- `--start`：回测开始日期
- `--end`：回测结束日期

#### batch_backtest_V3.py

批量回测，支持多策略、多股票批量回测。

```bash
# 批量回测前50只股票
python backtest/strategy_backtest/batch_backtest_V3.py -l 50

# 指定策略
python backtest/strategy_backtest/batch_backtest_V3.py -l 50 --strategy B1
```

### 交易系统 (scripts/)

#### run_stock_trade.py

主交易入口，根据信号执行交易操作。

```bash
python scripts/run_stock_trade.py
```

### 数据库 (database/)

#### db_manager.py

DatabaseManager提供数据库CRUD操作。

```python
from database.db_manager import DatabaseManager

db = DatabaseManager()
# 插入数据
db.insert('daily_price', df)
# 查询数据
df = db.query('daily_price', {'code': '600000'})
```

#### schema.py

数据库表结构定义

### 策略系统 (strategies/)

#### framework_strategy.py

策略基类，所有自定义策略需继承此类并重写相关方法。

```python
from strategies.base.framework_strategy import FrameworkStrategy

class MyStrategy(FrameworkStrategy):
    def __init__(self):
        super().__init__()
    
    def next(self):
        # 策略逻辑
        pass
```

### AI集成 (agent_integration/)

#### llm_adapter.py

LLM适配器，集成大语言模型进行交易决策辅助。

#### trading_graph.py

交易图模块，可视化交易决策流程。

### Web仪表板 (dashboard/)

#### app.py

Flask Web应用，提供交易状态监控和统计分析界面。

```bash
cd dashboard
python app.py
```

## 数据库表结构

### daily_price (日线数据)

| 字段 | 类型 | 说明 |
|------|------|------|
| code | VARCHAR | 股票代码 |
| date | DATE | 日期 |
| open | FLOAT | 开盘价 |
| high | FLOAT | 最高价 |
| low | FLOAT | 最低价 |
| close | FLOAT | 收盘价 |
| volume | BIGINT | 成交量 |
| amount | FLOAT | 成交额 |

### daily_signals (每日信号)

| 字段 | 类型 | 说明 |
|------|------|------|
| code | VARCHAR | 股票代码 |
| date | DATE | 日期 |
| signal_type | VARCHAR | 信号类型 |
| signal_value | FLOAT | 信号值 |
| strategy | VARCHAR | 策略名称 |

### positions (持仓)

| 字段 | 类型 | 说明 |
|------|------|------|
| code | VARCHAR | 股票代码 |
| shares | INTEGER | 持仓数量 |
| avg_cost | FLOAT | 平均成本 |
| update_date | DATE | 更新日期 |

### backtest_run (回测记录)

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | VARCHAR | 回测ID |
| strategy | VARCHAR | 策略名称 |
| start_date | DATE | 开始日期 |
| end_date | DATE | 结束日期 |
| total_return | FLOAT | 总收益 |
| sharpe_ratio | FLOAT | 夏普比率 |

### backtest_trades (回测交易记录)

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | VARCHAR | 回测ID |
| trade_date | DATE | 交易日期 |
| action | VARCHAR | 买入/卖出 |
| code | VARCHAR | 股票代码 |
| price | FLOAT | 价格 |
| shares | INTEGER | 数量 |

### backtest_performance (回测绩效)

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | VARCHAR | 回测ID |
| total_return | FLOAT | 总收益 |
| annualized_return | FLOAT | 年化收益 |
| max_drawdown | FLOAT | 最大回撤 |
| sharpe_ratio | FLOAT | 夏普比率 |
| win_rate | FLOAT | 胜率 |

## 配置说明

### settings.py

系统配置文件位于 `config/settings.py`

```python
# 数据源配置
DATA_SOURCE_PRIORITY = ['tushare', 'baostock']

# 回测配置
INITIAL_CASH = 1000000  # 初始资金
COMMISSION = 0.0003     # 手续费

# 策略配置
STRATEGY_PARAMS = {
    'B1': {'kdj_threshold': 13, 'score_threshold': 8},
    'B2': {'rsi_threshold': 21, 'gain_threshold': 3.95},
}
```

## 使用示例

### 完整回测流程

```bash
# 1. 更新股票列表
python data/updaters/fetcher_all_stockV3.py

# 2. 下载日线数据
python data/updaters/fetcher_daily_priceV4.py --start-date 20240101

# 3. 扫描信号
python signals/scan_signals_v2.py --date 20260330 --workers 10

# 4. 批量回测
python backtest/strategy_backtest/batch_backtest_V3.py -l 100

# 5. 执行交易
python scripts/run_stock_trade.py
```

### 单股票回测

```bash
python backtest/strategy_backtest/run_backtest.py \
    -s 300486 \
    --start 20240101 \
    --end 20260330 \
    --strategy B1
```

### 多策略对比

```bash
# 回测B1策略
python backtest/strategy_backtest/batch_backtest_V3.py -l 50 --strategy B1

# 回测B2策略
python backtest/strategy_backtest/batch_backtest_V3.py -l 50 --strategy B2
```

### 查看Web仪表板

```bash
cd dashboard
python app.py
# 访问 http://localhost:5004
```

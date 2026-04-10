# 日志系统统一管理计划

## 目标

将所有日志统一到 `logs/` 目录下，按功能分类并使用日期分割。

## 目录结构

```
logs/
├── pipeline/                      # 核心数据流水线日志
│   ├── fetcher_dwd_{YYYYMMDD}.log      # 数据更新日志
│   ├── scan_signals_{YYYYMMDD}.log     # 信号扫描日志
│   └── workflow_{YYYYMMDD}.log         # 工作流调度日志
├── backtest/                      # 回测日志
│   └── {strategy}_{YYYYMMDD}.log     # 按策略和日期分割
├── init/                         # 数据初始化日志
│   └── {table}_{YYYYMMDD}.log        # 按表名和日期分割
└── check/                        # 数据检查日志
    └── health_check_{YYYYMMDD}.log  # 健康检查日志
```

## 需要修改的脚本

### 1. 核心数据流水线 (logs/pipeline/)

| 脚本 | 当前日志路径 | 新日志路径 |
|------|-------------|-------------|
| `signals/scan_signals_v2.py` | `logs/scan_signals_{date}.log` | `logs/pipeline/scan_signals_{date}.log` |
| `data/updaters/fetcher_dwd.py` | `logs/fetcher_dwd.log` | `logs/pipeline/fetcher_dwd_{date}.log` |
| `scripts/workflow_scheduler.py` | 无文件日志 | `logs/pipeline/workflow_{date}.log` |
| `dashboard/data_update_api.py` | `logs/fetcher_dwd.log` | `logs/pipeline/fetcher_dwd_{date}.log` (读取) |

### 2. 回测日志 (logs/backtest/)

| 脚本 | 当前日志路径 | 新日志路径 |
|------|-------------|-------------|
| `backtest/strategy_backtest/run_backtest.py` | `results/{strategy}/{date}/backtest.log` | `logs/backtest/{strategy}_{date}.log` |
| `backtest/strategy_backtest/batch_backtest_V3.py` | `results/{strategy}/{date}/batch.log` | `logs/backtest/{strategy}_{date}.log` |

### 3. 数据初始化日志 (logs/init/)

| 脚本 | 当前日志路径 | 新日志路径 |
|------|-------------|-------------|
| `data/updaters/init_calendar.py` | 无文件日志 | `logs/init/calendar_{date}.log` |
| `data/updaters/init_stock_info.py` | 无文件日志 | `logs/init/stock_info_{date}.log` |

### 4. 数据检查日志 (logs/check/)

| 脚本 | 当前日志路径 | 新日志路径 |
|------|-------------|-------------|
| `scripts/data_check/check_data_source.py` | 无文件日志 | `logs/check/health_check_{date}.log` |

## 具体修改

### 1. 创建统一的日志工具模块

**新文件**: `scripts/log_utils.py`

```python
"""
日志工具模块 - 统一管理日志配置
"""
import logging
import os
from datetime import datetime

LOG_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')

def setup_logger(name: str, log_subdir: str, log_filename: str = None, date_suffix: bool = True) -> logging.Logger:
    """
    设置统一格式的日志记录器
    
    Args:
        name: logger名称
        log_subdir: 日志子目录 (pipeline/backtest/init/check)
        log_filename: 日志文件名 (不含日期)，默认使用name
        date_suffix: 是否添加日期后缀
    
    Returns:
        配置好的logger
    """
    # 创建日志目录
    log_dir = os.path.join(LOG_BASE_DIR, log_subdir)
    os.makedirs(log_dir, exist_ok=True)
    
    # 日志文件名
    if log_filename is None:
        log_filename = name
    if date_suffix:
        date_str = datetime.now().strftime('%Y%m%d')
        log_filename = f"{log_filename}_{date_str}"
    log_path = os.path.join(log_dir, f"{log_filename}.log")
    
    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    # 文件handler
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 格式
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
```

### 2. 修改 `signals/scan_signals_v2.py`

```python
# 删除当前的日志配置 (lines 62-80)
# LOG_DIR, LOG_FILE, logging.basicConfig 等

# 添加统一日志工具
from scripts.log_utils import setup_logger
logger = setup_logger('scan_signals', 'pipeline')

# 注意: scan_signals_v2 会创建子logger处理每只股票
# 这些子logger继承父logger的handler
```

### 3. 修改 `data/updaters/fetcher_dwd.py`

```python
# 删除当前的日志配置 (lines 69-78)
# LOG_PATH, file_handler 等

# 添加统一日志工具
from scripts.log_utils import setup_logger
logger = setup_logger('fetcher_dwd', 'pipeline')
```

### 4. 修改 `scripts/workflow_scheduler.py`

```python
# 添加统一日志工具
from scripts.log_utils import setup_logger
logger = setup_logger('workflow_scheduler', 'pipeline')
```

### 5. 修改 `backtest/strategy_backtest/run_backtest.py`

```python
# 删除自定义的TeeOutput类和相关日志逻辑
# 添加统一日志工具
from scripts.log_utils import setup_logger
logger = setup_logger(f'backtest_{strategy_name}', 'backtest')
```

### 6. 修改 `backtest/strategy_backtest/batch_backtest_V3.py`

```python
# 删除batch_log_file相关逻辑
# 添加统一日志工具
from scripts.log_utils import setup_logger
logger = setup_logger(f'batch_{strategy_name}', 'backtest')
```

### 7. 修改 `data/updaters/init_calendar.py`

```python
# 删除logging.basicConfig
# 添加统一日志工具
from scripts.log_utils import setup_logger
logger = setup_logger('init_calendar', 'init')
```

### 8. 修改 `data/updaters/init_stock_info.py`

```python
# 添加print日志工具
import scripts.log_utils as log_utils
logger = log_utils.setup_logger('init_stock_info', 'init')
# 替换print为logger.info
```

### 9. 修改 `scripts/data_check/check_data_source.py`

```python
# 添加统一日志工具
from scripts.log_utils import setup_logger
logger = setup_logger('health_check', 'check')
```

### 10. 修改 `dashboard/data_update_api.py`

```python
# 修改日志读取路径
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'pipeline', 'fetcher_dwd_{date}.log')
# 动态获取当前日期的文件路径
```

## 实施顺序

1. **Phase 1**: 创建 `scripts/log_utils.py` 工具模块
2. **Phase 2**: 修改核心流水线脚本 (scan_signals, fetcher_dwd, workflow_scheduler)
3. **Phase 3**: 修改回测脚本 (run_backtest, batch_backtest_V3)
4. **Phase 4**: 修改初始化脚本 (init_calendar, init_stock_info)
5. **Phase 5**: 修改检查脚本 (check_data_source)
6. **Phase 6**: 修改 Dashboard API

## 验证

修改后运行各脚本，检查日志是否正确写入 `logs/{子目录}/{name}_{date}.log`

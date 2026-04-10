# 计划: 修改 run_step_stock_info 使用 DWDFetcher

## 目标
将 `workflow_scheduler.py` 的 `run_step_stock_info()` 从使用 `fetcher_all_stockV3` 改为使用 `fetcher_dwd.DWDFetcher`

## 修改文件
`/Users/mawenhao/Desktop/code/股票策略/scripts/workflow_scheduler.py`

## 具体修改

### 1. 删除 fetcher_all_stockV3 导入 (第32行)

**修改前:**
```python
from data.updaters.fetcher_all_stockV3 import full_download as stock_full_download, incremental_download as stock_incremental_download
```

**修改后:**
删除此行（不再需要）

### 2. 修改 run_step_stock_info() 函数 (第159-187行)

**修改前:**
```python
def run_step_stock_info(pipeline_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """执行 stock_info 步骤"""
    start_time = datetime.now()
    mode = params.get('mode', 'full')
    
    if mode == 'full':
        count = stock_full_download()
    else:
        count = stock_incremental_download()
    
    with get_db_connection() as conn:
        actual_count = conn.execute("SELECT COUNT(*) FROM stock_info").fetchone()[0]
        delisted_count = conn.execute("SELECT COUNT(*) FROM stock_info WHERE is_delisted = TRUE").fetchone()[0]
        st_count = conn.execute("SELECT COUNT(*) FROM stock_info WHERE is_st = TRUE").fetchone()[0]
    
    write_step_log(pipeline_id, 'stock_info', {
        'update_type': mode,
        'start_time': start_time.isoformat(),
        'end_time': datetime.now().isoformat(),
        'expected_count': count or 0,
        'actual_count': actual_count,
        'is_success': True,
        'step_details': {
            'delisted_count': delisted_count,
            'st_stock_count': st_count,
        }
    })
    
    return {'success': True, 'records_count': actual_count}
```

**修改后:**
```python
def run_step_stock_info(pipeline_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """执行 stock_info 步骤"""
    start_time = datetime.now()
    
    # 从环境变量获取数据源，默认tushare
    source = os.environ.get('DATA_SOURCE', 'tushare')
    
    # 使用 DWDFetcher
    from data.updaters.fetcher_dwd import DWDFetcher
    fetcher = DWDFetcher(source=source)
    result = fetcher.update_stock_info(source=source)
    
    with get_db_connection() as conn:
        actual_count = conn.execute("SELECT COUNT(*) FROM dwd_stock_info").fetchone()[0]
    
    write_step_log(pipeline_id, 'stock_info', {
        'update_type': 'full',
        'start_time': start_time.isoformat(),
        'end_time': datetime.now().isoformat(),
        'expected_count': result.get('records', 0),
        'actual_count': actual_count,
        'is_success': result.get('success', 0) == 1,
        'data_source': source,
        'step_details': {
            'elapsed': result.get('elapsed', 0),
        }
    })
    
    return {'success': True, 'records_count': actual_count}
```

## 注意事项

1. **表名变更**: 从 `stock_info` (legacy) 改为 `dwd_stock_info` (DWD层)
2. **字段变更**: `dwd_stock_info` 没有 `is_delisted`, `is_st` 字段，所以统计信息简化
3. **增量模式**: 目前 DWDFetcher 的 `update_stock_info()` 不支持增量模式，只支持全量更新

## 验证

修改后运行:
```bash
python scripts/workflow_scheduler.py --run --pipeline daily --date 20260407 --skip-health-check
```

检查日志确认 `stock_info` 步骤成功执行。

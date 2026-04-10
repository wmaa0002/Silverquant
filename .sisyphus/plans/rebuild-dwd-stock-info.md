# 计划: 重建 dwd_stock_info 表

## 目标
删除现有 dwd_stock_info 表，根据 Tushare API 字段重建：
```
['ts_code', 'symbol', 'name', 'area', 'industry', 'market', 
 'list_date', 'is_hs', 'act_name', 'list_status', 'delist_date']
```

## 执行步骤

### 1. 删除现有 dwd_stock_info 表
```python
import duckdb
conn = duckdb.connect('data/Astock3.duckdb')
conn.execute('DROP TABLE IF EXISTS dwd_stock_info')
conn.close()
```

### 2. 更新 database/schema.py 中的表结构

修改 `CREATE_DWD_STOCK_INFO_TABLE`:
```python
CREATE_DWD_STOCK_INFO_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_stock_info (
    ts_code VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    name VARCHAR,
    area VARCHAR,
    industry VARCHAR,
    market VARCHAR,
    list_date DATE,
    is_hs VARCHAR,
    act_name VARCHAR,
    list_status VARCHAR,     -- 新增
    delist_date DATE,        -- 新增
    data_source VARCHAR DEFAULT 'tushare'
);
"""
```

### 3. 更新 fetcher_dwd.py 的 _update_stock_info_tushare() 方法

在保存前添加 list_status 和 delist_date 字段:
```python
df['list_status'] = 'L'  # 或从API返回的值
df['delist_date'] = None  # 或从API返回的值
```

### 4. 更新 scan_signals_v2.py 的 get_stock_list()

添加上市状态过滤:
```python
SELECT symbol AS code, name
FROM dwd_stock_info
WHERE list_status = 'L'  -- 只获取上市股票
ORDER BY symbol
```

### 5. 重新运行 stock_info 更新
```bash
python data/updaters/fetcher_dwd.py --data-type stock_info --source tushare
```

## 验证
```python
import duckdb
conn = duckdb.connect('data/Astock3.duckdb')
count = conn.execute("SELECT COUNT(*) FROM dwd_stock_info WHERE list_status = 'L'").fetchone()[0]
print(f'dwd_stock_info with L status: {count}')
conn.close()
```

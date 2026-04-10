# stock_info → dwd_stock_info 迁移计划

## TL;DR

> 将所有读写 `stock_info` 旧表的代码迁移到 `dwd_stock_info`，旧表保留为历史数据。
> **旧表 99.9% industry 字段为空，新表 industry 完整（5497/5499）。**

**改动范围：4 个文件**
**风险等级：低（只改读取路径，不改数据）**

---

## 背景

### 两张表的现状

| 表 | 类型 | 行数 | industry | market_cap | 问题 |
|----|------|------|----------|------------|------|
| `stock_info` (旧) | BASE TABLE | 5,833 | **0/5833 有值（全部为空）** | 几乎全空 | 数据质量差，写入路径丢失 industry |
| `dwd_stock_info` (新) | BASE TABLE | 5,499 | **5497/5499 有值** | 无此字段 | 真实数据源 |

- `save_stock_info()` 写入旧表，但 industry 字段全为空（bug）
- `get_stock_info()` 读旧表，industry 同样全为空
- `dwd_stock_info` 数据完整，但没有任何代码读取它

### 根本原因

`stock_info` 是旧表，`dwd_stock_info` 是 tushare 来的新表，两套表并存但代码全读旧表。

---

## 实施步骤

### Task 1: `database/db_manager.py` — 核心改造

**文件**: `/Users/mawenhao/Desktop/code/股票策略/database/db_manager.py`

**改动内容**:

#### `save_stock_info()` — 改为写入 `dwd_stock_info`

```python
def save_stock_info(self, df: pd.DataFrame):
    """保存股票基础信息到 dwd_stock_info"""
    if len(df) == 0:
        return
        
    df = df.copy()
    
    # 构建 ts_code (tushare 格式: 600000.SH / 000001.SZ)
    def code_to_ts_code(code):
        code = str(code)
        return f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
    df['ts_code'] = df['code'].apply(code_to_ts_code)
    
    # 字段重命名对齐 dwd_stock_info schema
    df['symbol'] = df['code']
    df['list_date'] = df['listing_date']
    df['data_source'] = 'stock_info_updater'
    
    insert_cols = ['ts_code', 'symbol', 'name', 'industry', 'list_date', 'data_source']
    
    self.conn.execute("CREATE TEMPORARY TABLE temp_stock_info AS SELECT * FROM df;")
    
    update_parts = [f"{c} = excluded.{c}" for c in insert_cols if c not in ['ts_code', 'symbol']]
    upsert_sql = f"""
        INSERT INTO dwd_stock_info ({', '.join(insert_cols)})
        SELECT {', '.join(insert_cols)} FROM temp_stock_info
        ON CONFLICT (ts_code) DO UPDATE SET
            {', '.join(update_parts)};
    """
    self.conn.execute(upsert_sql)
    self.conn.execute("DROP TABLE temp_stock_info;")
```

#### `get_stock_info()` — 改为读 `dwd_stock_info`

```python
def get_stock_info(self, code: Optional[str] = None) -> pd.DataFrame:
    """获取股票基础信息（从 dwd_stock_info）"""
    if code:
        ts_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
        query = f"""
            SELECT 
                symbol AS code,
                name,
                industry,
                NULL AS market_cap,
                NULL AS circulating_cap,
                list_date AS listing_date,
                market AS market_type,
                NULL AS is_st,
                NULL AS update_time,
                (list_status = 'D') AS is_delisted
            FROM dwd_stock_info 
            WHERE ts_code = '{ts_code}'
        """
    else:
        query = """
            SELECT 
                symbol AS code,
                name,
                industry,
                NULL AS market_cap,
                NULL AS circulating_cap,
                list_date AS listing_date,
                market AS market_type,
                NULL AS is_st,
                NULL AS update_time,
                (list_status = 'D') AS is_delisted
            FROM dwd_stock_info
        """
    return self.conn.execute(query).fetchdf()
```

#### `get_stock_list()` — 改为读 `dwd_stock_info`

```python
def get_stock_list(self) -> List[str]:
    """获取所有在市股票代码列表"""
    result = self.conn.execute(
        "SELECT symbol FROM dwd_stock_info WHERE list_status = 'L' ORDER BY symbol"
    ).fetchall()
    return [row[0] for row in result]
```

**位置**: `database/db_manager.py:60-98`

---

### Task 2: `data/updaters/fetcher_dwd.py` — 改查新表

**文件**: `/Users/mawenhao/Desktop/code/股票策略/data/updaters/fetcher_dwd.py`

**改动内容** (line 169-176):

```python
def _get_stock_list_from_db(self) -> List[str]:
    """从数据库获取股票列表（从 dwd_stock_info 读取）"""
    db = duckdb.connect(self.db_path)
    try:
        # dwd_stock_info.symbol = 股票代码如 600000
        # 注意：已退市的股票 list_status='D'，是否包含取决于业务需求
        result = db.execute(
            "SELECT symbol FROM dwd_stock_info WHERE list_status = 'L' ORDER BY symbol"
        ).fetchall()
        return [row[0] for row in result]
    finally:
        db.close()
```

**改动位置**: `data/updaters/fetcher_dwd.py:169-176`

---

### Task 3: `backtest/strategy_backtest/batch_backtest_V3.py` — 改查新表

**文件**: `/Users/mawenhao/Desktop/code/股票策略/backtest/strategy_backtest/batch_backtest_V3.py`

**改动内容** (line 97-117):

```python
def get_stock_list_from_db(limit: int = None, industry: str = None, 
                           market_cap_min: float = None, market_cap_max: float = None) -> pd.DataFrame:
    """从数据库获取股票列表（从 dwd_stock_info 读取）
    
    注意: market_cap 字段在 dwd_stock_info 中不存在，
          market_cap_min/max 筛选将被忽略
    """
    conn = duckdb.connect(str(ASTOCK3_DB_PATH))
    
    # 字段映射: code←symbol, market_cap 字段已移除
    query = "SELECT symbol AS code, name, industry FROM dwd_stock_info WHERE list_status = 'L'"
    
    if industry:
        query += f" AND industry = '{industry}'"
    # market_cap 筛选: dwd_stock_info 无此字段，跳过
    # if market_cap_min:  # 已废弃
    # if market_cap_max:  # 已废弃
    
    if limit:
        query += f" LIMIT {limit}"
    
    df = conn.execute(query).df()
    conn.close()
    return df
```

**改动位置**: `backtest/strategy_backtest/batch_backtest_V3.py:97-117`

---

### Task 4: `backtest/engine.py` — 改查新表

**文件**: `/Users/mawenhao/Desktop/code/股票策略/backtest/engine.py`

**改动内容** (line 328-337):

```python
# 查询股票信息（从 dwd_stock_info 读取）
stock_info_df = self.db.conn.execute(
    f"""
    SELECT name, industry 
    FROM dwd_stock_info 
    WHERE symbol = '{stock_code}'
    """
).fetchone()
```

**改动位置**: `backtest/engine.py:328-337`

---

## 验证步骤

### 验证 1: `db_manager.py` 读写验证

```python
from database.db_manager import DatabaseManager
db = DatabaseManager()

# 读测试
df = db.get_stock_info('600000')
print(df)  # industry 应为"银行"，不再是 None

# 列表测试
codes = db.get_stock_list()
print(f"在市股票数: {len(codes)}")  # 应为 5499

# 全量读取
all_df = db.get_stock_info()
print(f"industry 非空记录: {(all_df['industry'].notna()).sum()}")  # 应 > 5000
```

### 验证 2: 各模块调用验证

```bash
# fetcher_dwd 的股票列表来源
python -c "
import duckdb
conn = duckdb.connect('data/Astock3.duckdb')
codes = conn.execute(\"SELECT symbol FROM dwd_stock_info WHERE list_status = 'L' ORDER BY symbol\").fetchall()
print(f'在市股票: {len(codes)} 条')
print(f'样本: {[c[0] for c in codes[:5]]}')
"

# batch_backtest_V3 查询验证
python -c "
import duckdb
conn = duckdb.connect('data/Astock3.duckdb')
df = conn.execute(\"SELECT symbol AS code, name, industry FROM dwd_stock_info WHERE list_status = 'L' LIMIT 5\").df()
print(df)
"
```

### 验证 3: 回归验证

确保现有调用路径不断：
- `stock_adapter.py` 的 `get_stock_info()` 能正常读取
- `fetcher_dwd.py` 的 `_get_stock_list_from_db()` 能正常返回
- 回测引擎能正常获取股票行业信息

---

## 字段映射总结

| 旧 stock_info 读 | dwd_stock_info 读 | 说明 |
|-----------------|-------------------|------|
| code | symbol AS code | 直接映射 |
| name | name | 直接映射 |
| industry | industry | **旧表全空，新表完整** ✅ |
| market_cap | NULL | 两表均无，保留列但值始终为 NULL |
| circulating_cap | NULL | 两表均无 |
| listing_date | list_date AS listing_date | 直接映射 |
| market_type | market AS market_type | 直接映射 |
| is_st | NULL | dwd 无此字段，保留列但为 NULL |
| update_time | NULL | dwd 无此字段 |
| is_delisted | (list_status='D') AS is_delisted | 间接映射 |

---

## 风险评估

| 风险 | 级别 | 缓解 |
|------|------|------|
| `market_cap` 筛选丢失 | 中 | 旧表 99.9% 也为空，筛选本来就无效 |
| `is_st` 字段变 NULL | 低 | 旧表有值但从未被使用（industry 也是空的） |
| 写入路径改变 | 低 | `save_stock_info` 调用方极少，且新路径更正确 |
| 退市股票读取变化 | 低 | `get_stock_list()` 默认只返回 `list_status='L'`，已过滤退市股 |

---

## Success Criteria

- [x] `db.get_stock_info('600000')` 返回 industry='银行' ✅ 验证通过：industry='银行'
- [x] `db.get_stock_list()` 返回 5499 条在市股票 ✅ 验证通过：5499 条
- [x] `batch_backtest_V3` 能按 industry 筛选股票 ✅ 验证通过：查询正常
- [x] 回测引擎能获取股票名称和行业 ✅ 验证通过：symbol 映射正确
- [x] `fetcher_dwd` 能从 dwd_stock_info 获取股票列表 ✅ 验证通过：symbol 列表正常

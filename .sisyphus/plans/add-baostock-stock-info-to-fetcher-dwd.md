# 计划: 为 fetcher_dwd.py 添加 baostock stock_info 下载支持

## 问题描述

`fetcher_dwd.py` 的 `update_stock_info()` 方法目前**仅支持 tushare**，缺少 baostock 数据源支持。

当用户指定 `DATA_SOURCE=baostock` 时，`update_stock_info()` 仍会使用 tushare，无法完成 stock_info 更新。

## 现有代码分析

### 1. 目标表结构 (dwd_stock_info)

```sql
CREATE TABLE IF NOT EXISTS dwd_stock_info (
    ts_code VARCHAR PRIMARY KEY,     -- 股票代码: 600000.SH
    symbol VARCHAR,                  -- 符号: 600000
    name VARCHAR,                     -- 名称
    area VARCHAR,                     -- 地域
    industry VARCHAR,                 -- 行业
    market VARCHAR,                   -- 市场
    list_date DATE,                   -- 上市日期
    is_hs VARCHAR,                    -- 是否沪深港通
    act_name VARCHAR,                 -- 实控人名称
    data_source VARCHAR DEFAULT 'tushare'
);
```

### 2. 现有 Tushare 实现 (fetcher_dwd.py:724-756)

```python
def update_stock_info(self) -> Dict[str, Any]:
    """更新股票信息 (dwd_stock_info)"""
    from data.fetchers.tushare_adapter.base import TushareBaseFetcher
    base = TushareBaseFetcher()
    
    df = base.api.stock_basic(exchange='', list_status='L', 
        fields='ts_code,symbol,name,area,industry,market,list_date,is_hs,act_name')
    
    records = self._save_to_db(df, 'dwd_stock_info')
```

### 3. Baostock 数据源 (BaostockStockInfoFetcher)

```python
# stock_info.py 返回字段:
# - code: 600000.SH (tushare格式)
# - name: 股票名称
# - listing_date: 上市日期 (YYYY-MM-DD)
# - delist_date: 退市日期
# - is_delisted: 是否退市

# 注意: baostock 不提供 area, industry, market, is_hs, act_name
```

### 4. 字段映射

| dwd_stock_info 字段 | BaostockStockInfoFetcher | 说明 |
|---------------------|--------------------------|------|
| ts_code | code | ✅ 直接映射 |
| symbol | code.split('.')[0] | ✅ 需要转换 |
| name | name | ✅ 直接映射 |
| area | - | ❌ 无数据，设为 None |
| industry | - | ❌ 无数据，设为 None |
| market | - | ❌ 无数据，设为 None |
| list_date | listing_date | ✅ 直接映射 |
| is_hs | - | ❌ 无数据，设为 None |
| act_name | - | ❌ 无数据，设为 None |
| data_source | - | ✅ 设为 'baostock' |

---

## 实现方案

### 修改 `update_stock_info()` 方法

**文件**: `data/updaters/fetcher_dwd.py` 第724行附近

**当前签名**:
```python
def update_stock_info(self) -> Dict[str, Any]:
```

**新签名**:
```python
def update_stock_info(self, source: Optional[str] = None) -> Dict[str, Any]:
```

**实现逻辑**:

```python
def update_stock_info(self, source: Optional[str] = None) -> Dict[str, Any]:
    """
    更新股票信息 (dwd_stock_info)
    
    Args:
        source: 数据源 ('tushare' 或 'baostock')，默认使用 self.source
        
    Returns:
        更新统计信息
    """
    if source is None:
        source = self.source
    
    logger.info(f"开始更新股票信息, 数据源: {source}")
    
    if source == 'baostock':
        return self._update_stock_info_baostock()
    else:
        return self._update_stock_info_tushare()

def _update_stock_info_baostock(self) -> Dict[str, Any]:
    """使用 baostock 更新股票信息"""
    from data.fetchers.baostock_adapter import BaostockStockInfoFetcher
    
    start_time = time.time()
    
    try:
        fetcher = BaostockStockInfoFetcher()
        df = fetcher.fetch_all()
        
        if df is None or df.empty:
            logger.warning("Baostock 股票信息无数据")
            return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}
        
        # 字段映射
        df = df.rename(columns={
            'code': 'ts_code',
        })
        
        # 提取 symbol (去掉 .SH/.SZ 后缀)
        df['symbol'] = df['ts_code'].apply(lambda x: x.split('.')[0] if '.' in x else x)
        
        # 添加 baostock 缺失的字段
        df['area'] = None
        df['industry'] = None
        df['market'] = None
        df['is_hs'] = None
        df['act_name'] = None
        df['data_source'] = 'baostock'
        
        # 映射 listing_date 到 list_date
        df['list_date'] = df['listing_date']
        
        # 选择目标列
        target_cols = ['ts_code', 'symbol', 'name', 'area', 'industry', 'market', 
                       'list_date', 'is_hs', 'act_name', 'data_source']
        df = df[[col for col in target_cols if col in df.columns]]
        
        records = self._save_to_db(df, 'dwd_stock_info')
        elapsed = time.time() - start_time
        
        logger.info(f"股票信息更新完成 (baostock): {records}条, 耗时{elapsed:.1f}秒")
        return {'success': 1, 'fail': 0, 'records': records, 'elapsed': elapsed}
        
    except Exception as e:
        logger.error(f"更新股票信息失败 (baostock): {e}")
        return {'success': 0, 'fail': 1, 'records': 0, 'elapsed': 0}

def _update_stock_info_tushare(self) -> Dict[str, Any]:
    """使用 tushare 更新股票信息 (原有逻辑)"""
    # ... 现有代码 ...
```

### 修改 CLI 参数解析

**文件**: `data/updaters/fetcher_dwd.py` 约第884行

添加 `--source` 参数支持:

```python
parser.add_argument('--source', type=str, choices=['tushare', 'baostock'],
                    default=None, help='指定数据源')
```

在 main() 函数中传递给 `DWDFetcher` 或直接传递给 `update_stock_info()`:

```python
if args.source:
    source = args.source
else:
    source = os.environ.get('DATA_SOURCE', 'tushare')

if args.data_type == 'stock_info':
    fetcher = DWDFetcher(source=source)
    result = fetcher.update_stock_info(source=source)
```

---

## 任务清单

- [ ] 1. 修改 `update_stock_info()` 方法签名，添加 `source` 参数
- [ ] 2. 添加 `_update_stock_info_baostock()` 私有方法
- [ ] 3. 重构原有 tushare 逻辑为 `_update_stock_info_tushare()` 私有方法
- [ ] 4. 在 CLI main() 函数中添加 `--source` 参数解析
- [ ] 5. 更新 `update_stock_info()` 调用以传递 source 参数
- [ ] 6. 测试验证:
      - [ ] `python fetcher_dwd.py --data-type stock_info --source tushare`
      - [ ] `python fetcher_dwd.py --data-type stock_info --source baostock`
      - [ ] `DATA_SOURCE=baostock python fetcher_dwd.py --data-type stock_info`

---

## 测试验证

### 验证命令

```bash
# 测试 tushare (默认)
python data/updaters/fetcher_dwd.py --data-type stock_info --source tushare

# 测试 baostock
python data/updaters/fetcher_dwd.py --data-type stock_info --source baostock

# 环境变量方式
DATA_SOURCE=baostock python data/updaters/fetcher_dwd.py --data-type stock_info
```

### 预期结果

| 数据源 | 记录数 | list_date 字段 | data_source 字段 |
|--------|--------|----------------|------------------|
| tushare | ~5500 | 有 | 'tushare' |
| baostock | ~5000+ | 有 | 'baostock' |

---

## 注意事项

1. **字段缺失**: baostock 不提供 `area`, `industry`, `market`, `is_hs`, `act_name`，这些字段将设为 `None`

2. **增量更新**: 当前实现是全量覆盖，如果需要增量更新，需要额外逻辑

3. **退市股票**: baostock 返回的 `is_delisted` 字段可用于标记退市状态，但 dwd_stock_info 表结构中无此字段（需要在 schema 中确认）

4. **日期格式**: baostock 返回 `listing_date` 格式为 `YYYY-MM-DD`，与 tushare 一致

---

## 影响范围

- `data/updaters/fetcher_dwd.py` - 核心修改
- 测试脚本 `scripts/test_workflow.py` 无需修改（已使用环境变量 `DATA_SOURCE`）

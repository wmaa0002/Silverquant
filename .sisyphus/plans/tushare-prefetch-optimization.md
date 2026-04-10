# Prefetch 架构优化计划

## TL;DR

> **目标**: 将 `fetcher_daily_price_tushare.py` 的API调用次数从 **10000次(5000股票)** 降至 **2次**
> **方法**: 使用 Prefetch 架构，先一次性获取全市场数据，Workers 直接从内存提取

## 问题分析

### 当前架构

```
process_worker
  └→ download_single_stock
       └→ _get_daily_price_tushare_by_date
            └→ pro.daily(trade_date=)        # API调用1
            └→ pro.adj_factor(trade_date=)   # API调用2
```

**问题**: 每只股票都调用一次 `_get_daily_price_tushare_by_date`
- 5000只股票 = 5000 × 2 = **10000次API调用**
- 耗时: ~2小时

### 优化后架构

```
parallel_download_by_date
  └→ _get_daily_price_tushare_by_date(trade_date)  # API调用1: pro.daily
                                                 # API调用2: pro.adj_factor
  └→ 构建 market_data_dict {code: df_row}
  
process_worker_with_prefetch
  └→ 直接从 market_data_dict 提取，无API调用
```

**优化效果**: 
- 5000只股票 = **2次API调用**
- 耗时: ~3秒

---

## 实施方案

### T1: 新增 `process_worker_with_prefetch` 函数

**位置**: `data/updaters/fetcher_daily_price_tushare.py`

**实现**:
```python
def process_worker_with_prefetch(args):
    """多进程worker函数（使用预获取的全市场数据）
    
    Args:
        args: tuple of (process_id, stock_list, market_data_dict, target_table, db_path)
    
    Returns:
        tuple: (process_id, success_count, fail_count, failed_codes)
    """
    process_id, stock_list, market_data_dict, target_table, db_path = args
    
    success_count = 0
    fail_count = 0
    failed_codes = []
    
    try:
        logger.info(f"[{process_id}] 启动，待处理 {len(stock_list)} 只股票")
        
        for i, code in enumerate(stock_list):
            if code in market_data_dict:
                df = market_data_dict[code].copy()
                success_count += 1
                save_daily_price_to_db(df, db_path, target_table)
                if (i + 1) % 100 == 0:
                    logger.info(f"[{process_id}] 进度: {i+1}/{len(stock_list)}, 成功: {success_count}, 失败: {fail_count}")
            else:
                fail_count += 1
                failed_codes.append(code)
                logger.warning(f"[{process_id}] {code} 数据不存在")
    
    except Exception as e:
        logger.error(f"[{process_id}] 进程异常: {e}")
    
    logger.info(f"[{process_id}] 完成，成功: {success_count}，失败: {fail_count}")
    return (process_id, success_count, fail_count, failed_codes)
```

**验收标准**:
- [ ] 函数存在且可调用
- [ ] 能从 market_data_dict 正确提取数据

---

### T2: 新增 `run_download_round_with_prefetch` 函数

**位置**: `data/updaters/fetcher_daily_price_tushare.py`

**实现**:
```python
def run_download_round_with_prefetch(stock_list, market_data_dict, num_processes, target_table, db_path, round_name):
    """执行一轮下载（使用预获取的全市场数据）"""
    if not stock_list:
        logger.info(f"{round_name}: 无需下载")
        return [], 0, 0
    
    chunks = split_list(stock_list, num_processes)
    
    pool = Pool(num_processes)
    args_list = [
        (i, chunk, market_data_dict, target_table, db_path)
        for i, chunk in enumerate(chunks)
    ]
    
    results = [pool.apply_async(process_worker_with_prefetch, (args,)) for args in args_list]
    pool.close()
    pool.join()
    
    total_success = 0
    total_fail = 0
    all_failed_codes = []
    
    for result in results:
        proc_id, success_count, fail_count, failed_codes = result.get()
        total_success += success_count
        total_fail += fail_count
        all_failed_codes.extend(failed_codes)
    
    logger.info(f"{round_name} 完成: 成功 {total_success}, 失败 {total_fail}")
    return all_failed_codes, total_success, total_fail
```

**验收标准**:
- [ ] 函数存在且可调用
- [ ] 多进程分发正确

---

### T3: 修改 `parallel_download_by_date` 函数

**位置**: `data/updaters/fetcher_daily_price_tushare.py`
**修改内容**:

1. **新增 Prefetch 阶段**（在获取有效股票列表之前）:
```python
# ===== Prefetch 全市场数据 =====
logger.info("预获取全市场数据...")
df_all = _get_daily_price_tushare_by_date(trade_date)

market_data_dict = {}
for _, row in df_all.iterrows():
    market_data_dict[row['code']] = row.to_frame().T

logger.info(f"全市场数据已缓存，共 {len(market_data_dict)} 只股票")
# ===== Prefetch 结束 =====

# 获取有效股票列表
valid_stocks = get_valid_stock_list()
```

2. **修改缺失股票检查**:
```python
# 限制股票数量
if max_stocks is not None:
    valid_stocks = valid_stocks[:max_stocks]

# 检查哪些股票需要下载
stock_max_dates = get_stock_max_dates()
missing_stocks = []
for code in valid_stocks:
    if code not in market_data_dict:
        missing_stocks.append(code)  # 市场数据中没有
    elif stock_max_dates.get(code, '') >= trade_date:
        pass  # 已有最新数据，跳过
    else:
        missing_stocks.append(code)  # 需要更新

logger.info(f"待下载股票数: {len(missing_stocks)}")
```

3. **替换下载调用**:
```python
# 原: run_download_round(valid_stocks, ...)
# 改为:
failed_codes, success1, fail1 = run_download_round_with_prefetch(
    missing_stocks, market_data_dict,
    num_processes=1,
    target_table=target_table,
    db_path=db_path,
    round_name="第1轮"
)
```

4. **保留分级重试逻辑**（但使用 prefetch 版本）:
- 第2轮: 如果失败 > 5，调用 `run_download_round_with_prefetch`
- 第3轮+: 同上

**验收标准**:
- [ ] Prefetch 逻辑正确
- [ ] 缺失检查逻辑正确
- [ ] 分级重试使用 prefetch 版本

---

## API 调用次数对比

| 阶段 | 优化前 | 优化后 |
|------|--------|--------|
| Prefetch | 0 | 2次 (daily + adj_factor) |
| 每只股票 | 2次 × N | 0 |
| **5000只总计** | **10000次** | **2次** |

---

## 预期效果

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| API调用 | 10000次 | 2次 |
| 下载耗时 | ~2小时 | ~3秒 |
| 进程数 | 8进程仍慢 | 1进程足够 |

---

## 验证方法

```bash
# 测试：下载5只股票
python data/updaters/fetcher_daily_price_tushare.py --date 20260115 --max-stocks 5

# 预期：应该在5秒内完成
```

---

## 注意事项

1. **DuckDB 锁问题**: 多个进程同时写入DB会有锁冲突，这是预期的（可接受）
2. **内存占用**: market_data_dict 会占用一定内存（约几十MB），可接受
3. **保留原函数**: 保留 `process_worker` 和 `run_download_round` 以备后用
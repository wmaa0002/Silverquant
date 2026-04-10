# 计划: 过滤 baostock 数据只获取 status='1' 且 type='1'

## 目标
修改 `baostock_adapter/stock_info.py`，只获取 status='1'(上市) 且 type='1'(股票) 的数据

## 修改位置
`baostock_adapter/stock_info.py` 第62-65行之间

## 修改内容

在 `fetch_all()` 方法中，`构建DataFrame` 后、`转换格式` 前添加过滤：

```python
# 构建DataFrame
df = pd.DataFrame(data_list, columns=rs.fields)

# 过滤：只获取上市(status='1')的股票(type='1')
# baostock status: 1=上市, 0=退市
# baostock type: 1=股票, 2=指数, 4=转债, 5=ETF
df = df[(df['status'] == '1') & (df['type'] == '1')]

if df.empty:
    logger.warning("无上市股票信息返回")
    return self._empty_df()

# 转换格式
df = self._convert_format(df)
```

## 验证

修改后运行：
```python
from data.fetchers.baostock_adapter.stock_info import BaostockStockInfoFetcher
fetcher = BaostockStockInfoFetcher()
df = fetcher.fetch_all()
print(f'Count: {len(df)}')
print('market:', df['market'].value_counts().to_dict())
print('list_status:', df['list_status'].value_counts().to_dict())
```

预期结果：
- market: 只有"主板"（北交所、ETF、转债、指数都被过滤）
- list_status: 只有 'L'

# 计划: 修复 scan_signals_v2.py 代码格式不匹配问题

## 问题
- `get_stock_list()` 返回 `code` 格式: `600000`
- `get_stock_data()` 查询 `dwd_daily_price` 使用 `ts_code` 格式: `600000.SH`
- 格式不匹配导致所有股票查询失败

## 修改文件
`/Users/mawenhao/Desktop/code/股票策略/signals/scan_signals_v2.py`

## 修改内容

### 1. 添加代码转换函数 (在第49行后添加)

```python
def code_to_ts_code(code: str) -> str:
    """转换股票代码为tushare格式"""
    code = str(code)
    if code.startswith('6'):
        return f"{code}.SH"
    else:
        return f"{code}.SZ"
```

### 2. 修改 get_stock_data() 函数 (第134行)

**修改前:**
```python
def get_stock_data(code: str, trading_date: str, days: int = DATA_DAYS) -> Optional[pd.DataFrame]:
    """获取股票历史数据"""
    conn = get_db_connection()
    try:
        df = conn.execute("""
            SELECT ts_code, trade_date, open, high, low, close, vol
            FROM dwd_daily_price
            WHERE ts_code = ?
            AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        """, [code, trading_date, days]).fetchdf()
```

**修改后:**
```python
def get_stock_data(code: str, trading_date: str, days: int = DATA_DAYS) -> Optional[pd.DataFrame]:
    """获取股票历史数据"""
    conn = get_db_connection()
    try:
        # 转换 code 格式为 ts_code 格式
        ts_code = code_to_ts_code(code)
        
        df = conn.execute("""
            SELECT ts_code, trade_date, open, high, low, close, vol
            FROM dwd_daily_price
            WHERE ts_code = ?
            AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        """, [ts_code, trading_date, days]).fetchdf()
```

## 验证

修改后运行:
```bash
python signals/scan_signals_v2.py --date 2026-03-02 --workers 4
```

检查是否产生信号数据。

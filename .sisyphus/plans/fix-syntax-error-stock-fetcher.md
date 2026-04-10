# Fix: Syntax Error in Deprecated stock_fetcher.py

## Problem
Line 13 in `data/fetchers/stock_fetcher.py` contains Chinese characters outside the docstring:
```
13: 股票数据获取器 - 支持akshare、baostock和tushare三数据源
```
This causes `SyntaxError: invalid character '、' (U+3001)` when Python parses the file.

## Solution
Move line 13 inside the docstring (before the closing `"""`).

## Changes
```python
# BEFORE (broken):
"""
[DEPRECATED] ...
"""
股票数据获取器 - 支持akshare、baostock和tushare三数据源  # ← OUTSIDE docstring, causes SyntaxError
import akshare as ak

# AFTER (fixed):
"""
[DEPRECATED] ...
股票数据获取器 - 支持akshare、baostock和tushare三数据源  # ← INSIDE docstring
"""
import akshare as ak
```

## Execution
Use `quick` agent to fix the syntax error in `stock_fetcher.py`.

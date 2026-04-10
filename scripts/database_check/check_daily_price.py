#!/usr/bin/env python3
"""查看DuckDB数据库中daily_price表的数据量"""

import duckdb

DB_PATH = "/Users/mawenhao/Desktop/code/股票策略/data/Astock3.duckdb"


def main():
    conn = duckdb.connect(DB_PATH, read_only=True)
    
    # 查询总记录数
    result = conn.execute("SELECT COUNT(*) FROM dwd_daily_price").fetchone()
    total_count = result[0] if result else 0
    
    print(f"dwd_daily_price 表总记录数: {total_count:,}")
    
    # 按股票代码统计
    print("\n按股票代码统计 (前10):")
    stock_stats = conn.execute("""
        SELECT ts_code, COUNT(*) as cnt 
        FROM dwd_daily_price 
        GROUP BY ts_code 
        ORDER BY cnt DESC 
        LIMIT 10
    """).fetchall()
    
    for stock_code, cnt in stock_stats:
        print(f"  {stock_code}: {cnt:,} 条")
    
    # 按日期范围统计
    print("\n日期范围:")
    date_range = conn.execute("""
        SELECT MIN(trade_date) as min_date, MAX(trade_date) as max_date 
        FROM dwd_daily_price
    """).fetchone()
    
    if date_range:
        print(f"  从 {date_range[0]} 到 {date_range[1]}")
    
    conn.close()


if __name__ == "__main__":
    main()

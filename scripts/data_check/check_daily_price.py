"""
检查 daily_price 表数据情况
统计表中股票数量（去重）和每只股票的最新日线数据日期
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb
from datetime import datetime


DB_PATH = 'data/Astock3.duckdb'
# DB_PATH = 'data/test_quant.db'


def check_daily_price():
    """检查 daily_price 表数据"""
    print("=" * 60)
    print("检查 daily_price 表数据")
    print("=" * 60)
    
    db = duckdb.connect(DB_PATH)
    
    # 检查表是否存在
    tables = db.execute("SHOW TABLES").fetchall()
    if 'dwd_daily_price' not in [t[0] for t in tables]:
        print("dwd_daily_price 表不存在!")
        db.close()
        return
    
    # 统计股票数量（去重）
    stock_count = db.execute("SELECT COUNT(DISTINCT ts_code) FROM dwd_daily_price").fetchone()[0]
    print(f"股票数量（去重）: {stock_count}")
    
    # 统计总记录数
    total_count = db.execute("SELECT COUNT(*) FROM dwd_daily_price").fetchone()[0]
    print(f"总记录数: {total_count}")
    
    # 获取最新和最老的日期
    date_range = db.execute("""
        SELECT MIN(trade_date) as earliest, MAX(trade_date) as latest 
        FROM dwd_daily_price
    """).fetchone()
    print(f"\n日期范围: {date_range[0]} 至 {date_range[1]}")
    
    # 获取每只股票的最新日期
    print("\n每只股票的最新日线数据日期:")
    print("-" * 40)
    
    latest_dates = db.execute("""
        SELECT ts_code, MAX(trade_date) as latest_date 
        FROM dwd_daily_price 
        GROUP BY ts_code 
        ORDER BY latest_date DESC
    """).fetchdf()
    
    # 打印前20只股票
    print(latest_dates.head(20).to_string(index=False))
    
    if len(latest_dates) > 20:
        print(f"\n... 共 {len(latest_dates)} 只股票")
    
    # 统计最新日期分布
    print("\n最新日期分布:")
    date_distribution = db.execute("""
        SELECT latest_date, COUNT(*) as stock_count
        FROM (
            SELECT ts_code, MAX(trade_date) as latest_date 
            FROM dwd_daily_price 
            GROUP BY ts_code
        )
        GROUP BY latest_date
        ORDER BY latest_date DESC
        LIMIT 10
    """).fetchdf()
    print(date_distribution.to_string(index=False))
    
    # 统计每只股票的最早日期
    print("\n每只股票的最早日线数据日期（前20只）:")
    print("-" * 40)
    
    earliest_dates = db.execute("""
        SELECT ts_code, MIN(trade_date) as earliest_date 
        FROM dwd_daily_price 
        GROUP BY ts_code 
        ORDER BY earliest_date
    """).fetchdf()
    
    print(earliest_dates.head(20).to_string(index=False))
    
    db.close()
    print("\n检查完成!")


if __name__ == '__main__':
    check_daily_price()

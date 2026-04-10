"""
更新未完整更新股票的日线数据
只更新最新日期为2026-02-13的股票（缺失春节假期期间的数据）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import duckdb
import pandas as pd
from datetime import datetime, timedelta
import time
import random

from data.fetchers.stock_fetcher import StockFetcher
from data.fetchers.baostock_adapter.code_converter import to_tushare


DB_PATH = 'data/Astock3.duckdb'


def get_outdated_stocks():
    """获取需要更新的股票列表（最新日期为2026-02-13的股票）"""
    db = duckdb.connect(DB_PATH)
    
    outdated = db.execute("""
        SELECT ts_code, MAX(trade_date) as latest_date 
        FROM dwd_daily_price 
        GROUP BY ts_code 
        HAVING MAX(date) = '2026-02-13'
        ORDER BY code
    """).fetchdf()
    
    db.close()
    return outdated


def update_single_stock(code: str, start_date: str, end_date: str) -> tuple:
    """
    下载并保存单只股票的日线数据
    
    Returns:
        (success: bool, error_msg: str, records_count: int)
    """
    try:
        fetcher = StockFetcher()
        df = fetcher.get_daily_price(code, start_date, end_date, adjust='qfq')
        
        if df is None or len(df) == 0:
            return (False, '无数据', 0)
        
        df = df.copy()
        
        # 处理日期格式
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.date
        
        # 重命名列
        if '股票代码' in df.columns:
            df = df.rename(columns={'股票代码': 'code'})
        
        # 选择要插入的列
        cols = ['date', 'code', 'open', 'high', 'low', 'close', 'volume', 'amount']
        cols = [c for c in cols if c in df.columns]
        df_insert = df[cols].copy()
        
        # 插入数据库
        db = duckdb.connect(DB_PATH)
        try:
            for _, row in df_insert.iterrows():
                ts_code = to_tushare(row['code'])
                db.execute("""
                    INSERT OR REPLACE INTO dwd_daily_price 
                    (trade_date, ts_code, open, high, low, close, vol, amount, data_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [row['date'], ts_code, row['open'], row['high'], 
                      row['low'], row['close'], row['volume'], row['amount'], 'tushare'])
            return (True, '', len(df))
        finally:
            db.close()
            
    except Exception as e:
        return (False, str(e)[:50], 0)


def update_stocks(stock_codes: list, start_date: str, end_date: str):
    """更新指定股票的日线数据"""
    success_count = 0
    fail_count = 0
    fail_stocks = []
    
    print(f"=" * 60)
    print(f"开始更新 {len(stock_codes)} 只股票")
    print(f"日期范围: {start_date} - {end_date}")
    print(f"=" * 60)
    
    for i, code in enumerate(stock_codes):
        print(f"[{i+1}/{len(stock_codes)}] 正在下载 {code}...", end=' ')
        
        success, error_msg, count = update_single_stock(code, start_date, end_date)
        
        if success:
            success_count += 1
            print(f"成功 ({count}条)")
        else:
            fail_count += 1
            fail_stocks.append(code)
            print(f"失败: {error_msg}")
        
        # 每30只股票休眠
        if (i + 1) % 30 == 0:
            sleep_time = random.uniform(2, 3)
            print(f"已处理 {i+1} 只，休眠 {sleep_time:.1f} 秒...\n")
            time.sleep(sleep_time)
    
    return {
        'success_count': success_count,
        'fail_count': fail_count,
        'fail_stocks': fail_stocks
    }


def verify_update():
    """验证更新结果"""
    db = duckdb.connect(DB_PATH)
    
    count_25 = db.execute("""
        SELECT COUNT(DISTINCT ts_code) 
        FROM dwd_daily_price 
        WHERE trade_date = '2026-02-25'
    """).fetchone()[0]
    
    db.close()
    return {'count_2026_02_25': count_25}


def main():
    print("=" * 60)
    print("更新缺失日线数据")
    print("=" * 60)
    
    # 1. 获取需要更新的股票
    print("\n[1/3] 获取需要更新的股票...")
    outdated = get_outdated_stocks()
    stock_codes = outdated['code'].astype(str).tolist()
    print(f"需要更新的股票数量: {len(stock_codes)}")
    
    if len(stock_codes) == 0:
        print("没有需要更新的股票")
        return
    
    # 2. 更新数据
    print("\n[2/3] 开始更新数据...")
    result = update_stocks(stock_codes, '20260214', '20260224')
    
    # 3. 验证更新结果
    print("\n[3/3] 验证更新结果...")
    stats = verify_update()
    print(f"\n2026-02-25有数据: {stats['count_2026_02_25']} 只")
    
    print("\n" + "=" * 60)
    print(f"成功: {result['success_count']} 只")
    print(f"失败: {result['fail_count']} 只")
    
    if result['fail_stocks']:
        print(f"\n失败股票（前20只）:")
        for code in result['fail_stocks'][:20]:
            print(f"  {code}")
    
    print("\n更新完成!")


if __name__ == '__main__':
    main()

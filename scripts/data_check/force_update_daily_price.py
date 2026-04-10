"""
强制更新所有股票日线数据到最新日期
"""
import sys
import os
sys.path.insert(0, '.')

from data.fetchers.stock_fetcher import StockFetcher
from config.settings import Settings
import duckdb
from datetime import datetime
import time
import random

DB_PATH = 'data/Astock3.duckdb'
BATCH_SLEEP_COUNT = 100
BATCH_SLEEP_MIN = 3
BATCH_SLEEP_MAX = 5


def code_to_ts_code(code):
    """Convert 6-digit code to tushare format (6xxxxx.SH, others.SZ)"""
    code_str = str(code).zfill(6)
    if code_str.startswith('6') or code_str.startswith('688'):
        return f"{code_str}.SH"
    else:
        return f"{code_str}.SZ"


def get_all_stocks_with_data():
    """获取所有已有日线数据的股票"""
    db = duckdb.connect(DB_PATH)
    try:
        result = db.execute("SELECT DISTINCT ts_code FROM dwd_daily_price ORDER BY ts_code").fetchall()
        return [row[0] for row in result]
    finally:
        db.close()


def get_latest_date(code):
    """获取股票最新日期"""
    db = duckdb.connect(DB_PATH)
    try:
        result = db.execute(
            "SELECT MAX(trade_date) FROM dwd_daily_price WHERE ts_code = ?", [code]
        ).fetchone()
        return result[0].strftime('%Y%m%d') if result[0] else None
    finally:
        db.close()


def save_daily_price_to_db(df):
    """保存日线数据到数据库"""
    if df is None or len(df) == 0:
        return
    
    db = duckdb.connect(DB_PATH)
    try:
        df = df.copy()
        
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.date
        
        column_mapping = {
            '股票代码': 'code'
        }
        df = df.rename(columns=column_mapping)
        
        if 'code' in df.columns:
            df['ts_code'] = df['code'].apply(code_to_ts_code)
        
        if 'date' in df.columns:
            df['trade_date'] = df['date']
        
        if 'volume' in df.columns:
            df['vol'] = df['volume']
        
        if 'pct_change' in df.columns:
            df['pct_chg'] = df['pct_change']
        
        df['data_source'] = 'tushare'
        
        cols = ['trade_date', 'ts_code', 'open', 'high', 'low', 'close', 'vol', 
                'amount', 'turnover', 'pct_chg', 'data_source']
        
        cols = [c for c in cols if c in df.columns]
        df_insert = df[cols].copy()
        
        for col in df_insert.columns:
            dtype = str(df_insert[col].dtypes)
            if dtype == 'object':
                df_insert[col] = df_insert[col].replace(['None', ''], None)
        
        db.execute("CREATE TEMPORARY TABLE temp_price AS SELECT * FROM df_insert")
        insert_cols = ', '.join(df_insert.columns)
        db.execute(f"""
            INSERT OR REPLACE INTO dwd_daily_price ({insert_cols})
            SELECT {insert_cols} FROM temp_price
        """)
        db.execute("DROP TABLE temp_price")
    finally:
        db.close()


def force_update_all(start_date: str, end_date: str, progress: bool = True):
    """
    强制更新所有已有数据的股票到最新日期
    
    Args:
        start_date: 开始日期，格式YYYYMMDD
        end_date: 结束日期，格式YYYYMMDD
    """
    print("=" * 60)
    print("强制更新所有股票日线数据")
    print(f"日期范围: {start_date} - {end_date}")
    print("=" * 60)
    
    # 获取所有已有数据的股票
    stocks = get_all_stocks_with_data()
    print(f"已有日线数据的股票: {len(stocks)} 只")
    
    # 获取fetcher
    fetcher = StockFetcher(source=Settings.DATA_SOURCE)
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    fail_stocks = []
    
    for i, code in enumerate(stocks):
        # 检查当前最新日期
        current_latest = get_latest_date(code)
        
        # 比较是否需要更新
        if current_latest and int(current_latest) >= int(end_date):
            if progress and (i + 1) % 500 == 0:
                print(f"[{i+1}/{len(stocks)}] {code} 已是最新 ({current_latest})，跳过")
            skip_count += 1
            continue
        
        # 显示进度
        if progress:
            date_info = f"{current_latest or '无数据'} -> {end_date}"
            print(f"[{i+1}/{len(stocks)}] 正在更新 {code} ({date_info})...")
        
        # 下载数据
        try:
            df = fetcher.get_daily_price(
                code=code,
                start_date=start_date,
                end_date=end_date,
                adjust='qfq'
            )
            
            if df is not None and len(df) > 0:
                save_daily_price_to_db(df)
                success_count += 1
                if progress:
                    print(f"  -> 成功更新 {len(df)} 条数据")
            else:
                fail_count += 1
                fail_stocks.append(code)
                if progress:
                    print(f"  -> 无数据返回")
        except Exception as e:
            fail_count += 1
            fail_stocks.append(code)
            if progress:
                print(f"  -> 失败: {str(e)[:50]}")
        
        # 每100只股票休眠
        if (i + 1) % BATCH_SLEEP_COUNT == 0:
            sleep_time = random.uniform(BATCH_SLEEP_MIN, BATCH_SLEEP_MAX)
            print(f"已更新 {i+1} 只，休眠 {sleep_time:.1f} 秒...")
            time.sleep(sleep_time)
    
    # 统计结果
    result = {
        "total_stocks": len(stocks),
        "success_count": success_count,
        "fail_count": fail_count,
        "skip_count": skip_count,
        "fail_stocks": fail_stocks[:20]
    }
    
    print("\n" + "=" * 60)
    print("强制更新完成 - 统计报告")
    print("=" * 60)
    print(f"总股票数:     {result['total_stocks']}")
    print(f"成功更新:     {result['success_count']}")
    print(f"下载失败:     {result['fail_count']}")
    print(f"已是最新:     {result['skip_count']}")
    if result['fail_stocks']:
        print(f"失败股票:     {', '.join(result['fail_stocks'][:10])}...")
    print("=" * 60)
    
    return result


if __name__ == '__main__':
    import pandas as pd
    
    # 运行强制更新
    # 更新从 20260225 到今天的数据
    result = force_update_all('20260225', '20260226', progress=True)
    print(result)

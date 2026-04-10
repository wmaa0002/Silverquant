"""
初始化交易日历表 dwd_trade_calendar

从tushare获取2020-01-01至今的交易日历数据
支持SSE（上海）和SZSE（深圳）两个交易所
"""
import sys
import os
from datetime import datetime, date
from typing import List

import pandas as pd
import tushare as ts
import duckdb
# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config.settings import Settings
from data.fetchers.rate_limiter import tushare_limiter
from scripts.log_utils import setup_logger

logger = setup_logger('init_calendar', 'init')

# tushare pro API
_tushare_pro = None


def ensure_tushare_login() -> bool:
    """确保Tushare登录已建立"""
    global _tushare_pro
    if _tushare_pro is None:
        token = Settings.TUSHARE_TOKEN
        if not token:
            logger.error("TUSHARE_TOKEN未设置，无法使用tushare数据源")
            return False
        ts.set_token(token)
        _tushare_pro = ts.pro_api()
        logger.info("Tushare登录成功")
    return True


def fetch_trade_calendar(exchange: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    从tushare获取交易日历
    
    Args:
        exchange: 交易所代码，SSE（上海）或SZSE（深圳）
        start_date: 开始日期，格式YYYYMMDD
        end_date: 结束日期，格式YYYYMMDD
    
    Returns:
        包含trade_date, exchange, is_open列的DataFrame
    """
    if not ensure_tushare_login():
        return pd.DataFrame()
    
    tushare_limiter.acquire()
    
    try:
        df = _tushare_pro.trade_cal(
            exchange=exchange,
            start_date=start_date,
            end_date=end_date
        )
        
        if df is None or df.empty:
            logger.warning(f"pro.trade_cal返回空数据，exchange={exchange}, {start_date}-{end_date}")
            return pd.DataFrame()
        
        logger.info(f"获取到 {len(df)} 条日历记录，exchange={exchange}, {start_date}-{end_date}")
        return df
        
    except Exception as e:
        logger.error(f"获取交易日历失败: {e}")
        return pd.DataFrame()


def convert_cal_date(ts_code: str) -> str:
    """将tushare的TS指数代码转换为标准代码格式"""
    return ts_code


def init_calendar(db_path: str, start_date: str = '20200101', end_date: str = None) -> int:
    """
    初始化交易日历表
    
    Args:
        db_path: 数据库路径
        start_date: 开始日期，格式YYYYMMDD，默认20200101
        end_date: 结束日期，格式YYYYMMDD，默认今天
    
    Returns:
        插入的记录数
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    
    exchanges = ['SSE', 'SZSE']  # 上海交易所、深圳交易所
    all_records = []
    
    for exchange in exchanges:
        logger.info(f"正在获取 {exchange} 交易所日历...")
        df = fetch_trade_calendar(exchange, start_date, end_date)
        
        if df.empty:
            logger.warning(f"{exchange} 交易所获取数据为空")
            continue
        
        # 标准化数据
        df = df.rename(columns={
            'cal_date': 'trade_date',
            'exchange': 'exchange',
            'is_open': 'is_open'
        })
        
        # 转换日期格式：YYYYMMDD -> YYYY-MM-DD
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
        
        # 转换is_open为布尔值
        df['is_open'] = df['is_open'] == 1
        
        # 只保留需要的列
        df = df[['trade_date', 'exchange', 'is_open']]
        
        all_records.append(df)
    
    if not all_records:
        logger.error("没有获取到任何日历数据")
        return 0
    
    # 合并所有交易所数据
    df_all = pd.concat(all_records, ignore_index=True)
    
    # 插入数据库
    conn = duckdb.connect(db_path)
    try:
        # 先删除已存在的数据（如果表已存在且有数据）
        conn.execute(f"DELETE FROM dwd_trade_calendar WHERE trade_date >= '{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}'")
        
        # 插入新数据 - 使用executemany
        records_list = df_all[['trade_date', 'exchange', 'is_open']].values.tolist()
        
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO dwd_trade_calendar (trade_date, exchange, is_open) VALUES (?, ?, ?)",
            records_list
        )
        conn.commit()
        
        count = len(records_list)
        logger.info(f"成功插入 {count} 条交易日历记录")
        return count
        
    except Exception as e:
        logger.error(f"插入数据失败: {e}")
        raise
    finally:
        conn.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='初始化交易日历表 dwd_trade_calendar')
    parser.add_argument('--start', type=str, default='20200101',
                        help='开始日期，格式YYYYMMDD，默认20200101')
    parser.add_argument('--end', type=str, default=None,
                        help='结束日期，格式YYYYMMDD，默认今天')
    parser.add_argument('--db', type=str, default=None,
                        help=f'数据库路径，默认{Settings.DATABASE_PATH}')
    
    args = parser.parse_args()
    
    db_path = args.db or str(Settings.DATABASE_PATH)
    
    logger.info(f"开始初始化交易日历表...")
    logger.info(f"数据库路径: {db_path}")
    logger.info(f"日期范围: {args.start} - {args.end or '今天'}")
    
    count = init_calendar(db_path, args.start, args.end)
    
    logger.info(f"初始化完成，共插入 {count} 条记录")
    
    # 验证：检查2026-04-04是否为非交易日
    conn = duckdb.connect(db_path)
    try:
        result = conn.execute(
            "SELECT is_open FROM dwd_trade_calendar WHERE trade_date = '2026-04-04'"
        ).fetchone()
        if result:
            logger.info(f"验证: 2026-04-04 is_open = {result[0]} (预期: False)")
        else:
            logger.warning("验证: 2026-04-04 无数据")
    finally:
        conn.close()


if __name__ == '__main__':
    main()

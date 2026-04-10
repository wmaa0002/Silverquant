"""
初始化dwd_stock_info表 - 从tushare获取股票基本信息
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import duckdb
from datetime import datetime
from scripts.log_utils import setup_logger

logger = setup_logger('init_stock_info', 'init')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'Astock3.duckdb')


def get_tushare_api():
    """获取tushare pro API"""
    try:
        import tushare as ts
        pro = ts.pro_api(os.environ.get('TUSHARE_TOKEN', ''))
        return pro
    except Exception as e:
        logger.error(f"tushare登录失败: {e}")
        return None


def fetch_stock_basic():
    """
    从tushare获取stock_basic数据
    
    Returns:
        DataFrame with columns: ts_code, symbol, name, area, industry, market, list_date, is_hs, act_name
    """
    pro = get_tushare_api()
    if pro is None:
        return pd.DataFrame()
    
    try:
        # 获取所有上市股票 (list_status='L')
        df = pro.stock_basic(
            exchange='',
            list_status='L',
            fields='ts_code,symbol,name,area,industry,market,list_date,is_hs,act_name,list_status'
        )
        return df
    except Exception as e:
        logger.error(f"获取stock_basic失败: {e}")
        return pd.DataFrame()


def init_dwd_stock_info():
    """
    初始化dwd_stock_info表
    先删除旧数据，再插入新数据
    """
    logger.info("初始化dwd_stock_info表")
    
    # 获取数据
    logger.info("正在从tushare获取股票基本信息...")
    df = fetch_stock_basic()
    
    if df is None or df.empty:
        logger.error("获取数据失败!")
        return 0
    
    logger.info(f"获取到 {len(df)} 只股票")
    
    # 转换list_date为正确格式
    if 'list_date' in df.columns:
        df['list_date'] = pd.to_datetime(df['list_date'], format='%Y%m%d', errors='coerce')
    
    # 添加data_source字段
    df['data_source'] = 'tushare'
    
    # 保存到数据库
    db = duckdb.connect(DB_PATH)
    try:
        # 确保表存在
        from database.schema import CREATE_DWD_STOCK_INFO_TABLE
        db.execute(CREATE_DWD_STOCK_INFO_TABLE)
        
        # 清空旧数据（保留历史记录但重建）
        db.execute("DELETE FROM dwd_stock_info")
        
        # 使用临时表插入
        db.execute("CREATE TEMPORARY TABLE temp_stock AS SELECT * FROM df")
        
        insert_cols = 'ts_code, symbol, name, area, industry, market, list_date, is_hs, act_name, list_status, data_source'
        db.execute(f"INSERT INTO dwd_stock_info ({insert_cols}) SELECT {insert_cols} FROM temp_stock")
        db.execute("DROP TABLE temp_stock")
        
        # 验证
        count = db.execute("SELECT COUNT(*) FROM dwd_stock_info WHERE list_status = 'L'").fetchone()[0]
        logger.info(f"初始化完成! 共插入 {count} 只股票")
        
        return count
    finally:
        db.close()


def main():
    count = init_dwd_stock_info()
    
    # 验证
    if count >= 5000:
        logger.info(f"验证通过: {count} >= 5000")
    else:
        logger.warning(f"验证失败: {count} < 5000")


if __name__ == "__main__":
    main()

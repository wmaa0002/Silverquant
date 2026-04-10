"""
检查 baostock 数据源是否已更新到当前日期
测试 _get_daily_price_baostock 接口返回的数据是否最新
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import baostock as bs
from datetime import datetime, timedelta
import pandas as pd


def check_baostock_update(sample_stocks: list = None):
    """
    检查 baostock 数据源是否已更新到当前日期
    
    Args:
        sample_stocks: 采样测试的股票代码列表，默认使用部分热门股票
    """
    print("=" * 60)
    print("检查 baostock 数据源更新状态")
    print("=" * 60)
    
    # 登录 baostock
    lg = bs.login()
    if lg.error_code != '0':
        print(f"❌ baostock 登录失败: {lg.error_msg}")
        return
    
    print(f"✅ baostock 登录成功")
    
    # 默认采样股票（沪市和深市各选几只）
    if sample_stocks is None:
        sample_stocks = [
            '600000',  # 浦发银行
            '600519',  # 贵州茅台
            '000001',  # 平安银行
            '000002',  # 万 科Ａ
            '300001',  # 睿创微纳
            '688001',  # 华兴源创
        ]
    
    # 获取当前日期
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    
    # 判断当前是否为交易日（简单判断：工作日且非周末）
    is_trading_day = today.weekday() < 5
    
    print(f"\n当前日期: {today_str} (星期{today.isoweekday()})")
    print(f"当前是否为交易时段: {'是' if is_trading_day else '否'}")
    print("\n" + "-" * 60)
    print("采样测试结果:")
    print("-" * 60)
    
    update_count = 0
    not_update_count = 0
    
    for code in sample_stocks:
        # 转换代码格式
        if code.startswith('6'):
            bs_code = f"sh.{code}"
        else:
            bs_code = f"sz.{code}"
        
        # 获取最新数据
        rs = bs.query_history_k_data_plus(
            bs_code,
            'date',
            start_date=(today - timedelta(days=30)).strftime('%Y-%m-%d'),  # 最近30天
            end_date=today_str,
            frequency='d',
            adjustflag='2'  # 前复权
        )
        
        if rs.error_code != '0':
            print(f"  {code}: ❌ 获取失败 - {rs.error_msg}")
            continue
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            print(f"  {code}: ⚠️ 无数据")
            continue
        
        # 获取最新日期
        latest_date = data_list[-1][0]  # 最后一条记录的日期
        latest_date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
        
        # 检查是否已更新到最新交易日的上一个交易日
        # 如果今天是交易日，应该能看到今天或昨天的数据
        # 如果今天是周末，应该能看到周五的数据
        if is_trading_day:
            # 找到上一个交易日
            prev_trading_day = today - timedelta(days=1)
            while prev_trading_day.weekday() >= 5:  # 跳过周末
                prev_trading_day -= timedelta(days=1)
            
            expected_date = prev_trading_day.strftime('%Y-%m-%d')
        else:
            # 周末：找到上一个周五
            days_since_friday = (today.weekday() - 4) % 7
            if days_since_friday == 0:
                days_since_friday = 7
            prev_trading_day = today - timedelta(days=days_since_friday)
            expected_date = prev_trading_day.strftime('%Y-%m-%d')
        
        # 判断状态
        if latest_date >= expected_date:
            status = "✅ 已更新"
            update_count += 1
        else:
            status = "❌ 未更新"
            not_update_count += 1
        
        print(f"  {code}: 最新={latest_date}, 预期≥{expected_date} {status}")
    
    # 登出
    bs.logout()
    
    print("\n" + "=" * 60)
    print("总结:")
    print("=" * 60)
    print(f"  测试股票数: {len(sample_stocks)}")
    print(f"  已更新到最新: {update_count} 只")
    print(f"  未更新到最新: {not_update_count} 只")
    
    if update_count == len(sample_stocks):
        print(f"\n✅ baostock 数据源已更新到当前日期")
    else:
        print(f"\n⚠️ baostock 数据源尚未完全更新")
    
    print("=" * 60)


def check_baostock_with_db_compare():
    """
    对比 baostock 数据源与数据库中的数据
    """
    print("\n" + "=" * 60)
    print("对比 baostock 与数据库数据")
    print("=" * 60)
    
    import duckdb
    
    DB_PATH = 'data/Astock3.duckdb'
    db = duckdb.connect(DB_PATH)
    
    # 获取数据库中最新日期分布
    print("\n数据库中最新日期分布:")
    date_distribution = db.execute("""
        SELECT latest_date, COUNT(*) as stock_count
        FROM (
            SELECT ts_code, MAX(trade_date) as latest_date 
            FROM dwd_daily_price 
            GROUP BY ts_code
        )
        GROUP BY latest_date
        ORDER BY latest_date DESC
        LIMIT 5
    """).fetchdf()
    
    if not date_distribution.empty:
        print(date_distribution.to_string(index=False))
        db_latest = date_distribution.iloc[0]['latest_date']
        print(f"\n数据库最新日期: {db_latest}")
    else:
        print("数据库中无数据")
        db_latest = None
    
    db.close()
    
    # 获取 baostock 最新数据
    print("\nbaostock 最新数据:")
    lg = bs.login()
    if lg.error_code != '0':
        print(f"❌ 登录失败")
        return
    
    # 测试几只股票
    test_stocks = ['600519', '000001']
    today = datetime.now()
    
    for code in test_stocks:
        bs_code = f"sh.{code}" if code.startswith('6') else f"sz.{code}"
        
        rs = bs.query_history_k_data_plus(
            bs_code,
            'date',
            start_date=(today - timedelta(days=10)).strftime('%Y-%m-%d'),
            end_date=today.strftime('%Y-%m-%d'),
            frequency='d',
            adjustflag='2'
        )
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if data_list:
            latest = data_list[-1][0]
            print(f"  {code}: {latest}")
    
    bs.logout()


if __name__ == '__main__':
    # 执行检查
    check_baostock_update()
    
    # 可选：对比数据库
    # check_baostock_with_db_compare()

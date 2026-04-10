#!/usr/bin/env python3
"""
补全 portfolio_daily 表脚本
从 positions 和 daily_price 表反推历史每日资金状况
"""
import sys
sys.path.insert(0, '/Users/mawenhao/Desktop/code/股票策略/scripts')

import duckdb
from datetime import date, datetime

DB_PATH = '/Users/mawenhao/Desktop/code/股票策略/data/Astock3.duckdb'
INIT_CASH = 500000

def backfill_portfolio_daily():
    conn = duckdb.connect(DB_PATH)
    
    # 获取所有持仓记录
    positions = conn.execute('''
        SELECT code, name, strategy, shares, buy_price, status, profit_loss, buy_date, sell_date
        FROM positions ORDER BY buy_date
    ''').fetchall()
    
    # 获取所有有信号的交易日（从2026年开始）
    trade_dates = [d[0] for d in conn.execute('''
        SELECT DISTINCT date FROM daily_signals 
        WHERE date >= '2026-01-01' 
        ORDER BY date
    ''').fetchall()]
    
    # 过滤出相关的交易日期（从第一笔买入开始）
    relevant_dates = [d for d in trade_dates if d >= date(2026, 3, 13)]
    
    # 获取当前最大id（DuckDB不会自动自增，需要手动管理）
    next_id = conn.execute('SELECT COALESCE(MAX(id), 0) FROM portfolio_daily').fetchone()[0]
    
    # 检查是否已有数据
    existing = conn.execute('SELECT COUNT(*) FROM portfolio_daily').fetchone()[0]
    if existing > 0:
        print(f'⚠️  portfolio_daily 已有 {existing} 条记录，先清空？')
        confirm = input('输入 y 确认清空重建: ')
        if confirm.strip().lower() == 'y':
            conn.execute('DELETE FROM portfolio_daily')
            next_id = 0
            print('已清空，从头开始')
        else:
            print('取消操作')
            return
    
    records_inserted = 0
    for trade_date in relevant_dates:
        # 持仓: buy_date <= trade_date AND (sell_date > trade_date OR sell_date IS NULL)
        holding = [p for p in positions 
                   if p[7] <= trade_date and (p[8] is None or p[8] > trade_date)]
        
        # 已卖出: sell_date <= trade_date
        sold = [p for p in positions 
                if p[8] is not None and p[8] <= trade_date]
        
        # 计算持仓成本
        position_cost = sum(p[3] * p[4] * 1.0005 for p in holding)
        
        # 计算持仓市值
        position_value = 0
        holding_detail = []
        for p in holding:
            code, name, shares = p[0], p[1], p[3]
            cp = conn.execute(
                f"SELECT close FROM dwd_daily_price WHERE ts_code = '{code}' AND trade_date = '{trade_date}'"
            ).fetchone()
            if cp:
                val = shares * cp[0]
                position_value += val
                holding_detail.append(f'{name}({shares}股@{cp[0]:.2f})')
        
        # 计算已卖出盈亏
        closed_pnl = sum(p[6] for p in sold if p[6] is not None)
        
        position_pnl = position_value - position_cost
        total_pnl = position_pnl + closed_pnl
        available_cash = INIT_CASH - position_cost + closed_pnl
        position_ratio = position_value / INIT_CASH * 100
        
        # 生成notes
        if holding:
            notes = f"持仓{len(holding)}只: {','.join([p[1] for p in holding])}"
        else:
            notes = "空仓"
        if sold:
            notes += f" | 已卖{len(sold)}只: {','.join([p[1] for p in sold])}"
        
        # 插入（需要手动指定id）
        next_id += 1
        conn.execute(f"""
            INSERT INTO portfolio_daily (id, date, init_cash, position_cost, position_value, 
                position_pnl, closed_pnl, total_pnl, available_cash, position_ratio, notes)
            VALUES ({next_id}, '{trade_date}', {INIT_CASH}, {position_cost}, {position_value}, 
                {position_pnl}, {closed_pnl}, {total_pnl}, {available_cash}, {position_ratio}, '{notes}')
        """)
        
        records_inserted += 1
        print(f'✅ {trade_date}: 持仓{len(holding)}只 成本={position_cost:.0f} 市值={position_value:.0f} '
              f'持仓盈={position_pnl:.0f} 已卖盈={closed_pnl:.0f} 总盈={total_pnl:.0f} '
              f'仓位={position_ratio:.1f}%')
        if holding_detail:
            for h in holding_detail:
                print(f'    {h}')
    
    print(f'\n共插入 {records_inserted} 条记录到 portfolio_daily 表')
    
    # 验证
    rows = conn.execute('SELECT * FROM portfolio_daily ORDER BY date').fetchall()
    print(f'\n验证: portfolio_daily 现有 {len(rows)} 条记录')
    for r in rows:
        print(f'  {r[1]}: 成本={r[3]} 市值={r[4]} 总盈={r[7]} 仓位={r[9]}%')
    
    conn.close()

if __name__ == '__main__':
    backfill_portfolio_daily()

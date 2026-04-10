#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日持仓快照更新脚本 - update_portfolio_daily.py

用途：每日定时插入/更新 portfolio_daily 和 portfolio_daily_strategy 表
处理中国节假日和周末：非交易日沿用最近交易日数据

用法：
    python scripts/update_portfolio_daily.py              # 更新今日
    python scripts/update_portfolio_daily.py --date 20260327  # 更新指定日期
    python scripts/update_portfolio_daily.py --fix         # 强制更新（覆盖已有记录）
"""

import os
import sys
import argparse
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'Astock3.duckdb')
INIT_CASH = 500000.0
FEE_RATE = 0.0005  # 买入手续费 0.05%


def is_trading_day(check_date: date) -> bool:
    """判断是否为交易日（检查数据库中是否有当日价格数据）"""
    conn = duckdb.connect(DB_PATH, read_only=True)
    try:
        result = conn.execute(
            "SELECT COUNT(*) FROM dwd_daily_price WHERE trade_date = ?",
            [check_date.strftime('%Y-%m-%d')]
        ).fetchone()
        return result is not None and result[0] > 0
    finally:
        conn.close()


def get_latest_trading_day(before_date: date) -> date:
    """获取指定日期之前最近的交易日"""
    conn = duckdb.connect(DB_PATH, read_only=True)
    try:
        result = conn.execute(
            "SELECT MAX(trade_date) FROM dwd_daily_price WHERE trade_date < ?",
            [before_date.strftime('%Y-%m-%d')]
        ).fetchone()
        if result and result[0]:
            val = result[0]
            if isinstance(val, str):
                return date.fromisoformat(val)
            return val  # 已经是date对象
        return before_date
    finally:
        conn.close()


def get_target_date(target: date) -> tuple:
    """
    获取实际应该更新的日期
    Returns: (actual_date, is_holiday)
    """
    today = target

    # 周末直接找最近交易日
    if today.weekday() >= 5:
        latest = get_latest_trading_day(today)
        if latest != today:
            return latest, True

    # 检查是否是交易日
    if not is_trading_day(today):
        latest = get_latest_trading_day(today)
        if latest != today:
            return latest, True

    return today, False


def add_market_suffix(code: str) -> str:
    """将股票代码转换为带后缀的格式 (600642 -> 600642.SH, 300782 -> 300782.SZ)"""
    if code.startswith('6') or code.startswith('9') or code.startswith('5'):
        return f"{code}.SH"
    elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
        return f"{code}.SZ"
    elif code.startswith('4') or code.startswith('8'):
        return f"{code}.BJ"
    return code  # 未知格式返回原值


def update_portfolio_daily(target_date: date, force: bool = False):
    """插入/更新 portfolio_daily 和 portfolio_daily_strategy"""
    conn = duckdb.connect(DB_PATH, read_only=False)

    try:
        date_str = target_date.strftime('%Y-%m-%d')

        # ---- 检查是否已有记录 ----
        existing = conn.execute(
            "SELECT id FROM portfolio_daily WHERE date = ?", [date_str]
        ).fetchone()

        if existing and not force:
            print(f"portfolio_daily {date_str} 已存在，跳过（用 --fix 强制覆盖）")
            return False

        # ---- 获取持仓 ----
        holding = conn.execute(
            "SELECT code, name, shares, buy_price, strategy FROM positions WHERE status = 'holding'"
        ).fetchall()

        sold = conn.execute(
            "SELECT code, name, profit_loss FROM positions WHERE status = 'sold'"
        ).fetchall()

        # ---- 计算持仓市值 ----
        total_cost = 0.0
        total_value = 0.0
        holding_names = []

        for code, name, shares, buy_price, strategy in holding:
            cost = shares * buy_price * (1 + FEE_RATE)
            total_cost += cost

            price_row = conn.execute(
                "SELECT close FROM dwd_daily_price WHERE ts_code = ? AND trade_date = ?",
                [add_market_suffix(code), date_str]
            ).fetchone()

            if price_row and price_row[0]:
                value = shares * float(price_row[0])
                total_value += value

            holding_names.append(name)

        # ---- 计算已卖出盈亏 ----
        closed_pnl = 0.0
        sold_names = []
        for code, name, pl in sold:
            if pl is not None:
                closed_pnl += float(pl)
            sold_names.append(name)

        # ---- 汇总 ----
        position_pnl = total_value - total_cost
        total_pnl = position_pnl + closed_pnl
        available_cash = INIT_CASH - total_cost + closed_pnl
        total_value_account = total_value + available_cash
        position_ratio = (total_value / INIT_CASH * 100) if INIT_CASH > 0 else 0.0

        notes = "持仓%d只: %s" % (len(holding_names), ','.join(holding_names)) if holding_names else "空仓"
        if sold_names:
            notes += " | 已卖%d只: %s" % (len(sold_names), ','.join(sold_names[:5]))

        # ---- 操作 portfolio_daily ----
        if existing:
            conn.execute("DELETE FROM portfolio_daily WHERE date = ?", [date_str])
            print(f"覆盖已有记录: {date_str}")

        next_id = conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM portfolio_daily"
        ).fetchone()[0] + 1

        conn.execute("""
            INSERT INTO portfolio_daily
            (id, date, init_cash, position_cost, position_value, position_pnl,
             closed_pnl, total_pnl, available_cash, position_ratio, total_value, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [next_id, date_str, INIT_CASH, total_cost, total_value,
              position_pnl, closed_pnl, total_pnl, available_cash,
              position_ratio, total_value_account, notes])

        print("✅ portfolio_daily %s: 市值=%.0f 仓位=%.1f%% 总盈亏=%.0f" % (
            date_str, total_value, position_ratio, total_pnl))

        # ---- 操作 portfolio_daily_strategy ----
        strategies = {}
        for code, name, shares, buy_price, strategy in holding:
            if strategy not in strategies:
                strategies[strategy] = {'cost': 0.0, 'value': 0.0, 'count': 0}

            cost = shares * buy_price * (1 + FEE_RATE)
            strategies[strategy]['cost'] += cost
            strategies[strategy]['count'] += 1

            price_row = conn.execute(
                "SELECT close FROM dwd_daily_price WHERE ts_code = ? AND trade_date = ?",
                [add_market_suffix(code), date_str]
            ).fetchone()
            if price_row and price_row[0]:
                strategies[strategy]['value'] += shares * float(price_row[0])

        # 已卖出按策略分组
        for code, name, pl, strategy in conn.execute(
            "SELECT code, name, profit_loss, strategy FROM positions WHERE status = 'sold'"
        ).fetchall():
            if strategy not in strategies:
                strategies[strategy] = {'cost': 0.0, 'value': 0.0, 'count': 0}
            if pl is not None:
                if 'closed' not in strategies[strategy]:
                    strategies[strategy]['closed'] = 0.0
                strategies[strategy]['closed'] += float(pl)

        next_id_strat = conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM portfolio_daily_strategy"
        ).fetchone()[0]

        count = 0
        for strategy, data in strategies.items():
            if force:
                conn.execute(
                    "DELETE FROM portfolio_daily_strategy WHERE date = ? AND strategy = ?",
                    [date_str, strategy]
                )

            cost = data['cost']
            value = data['value']
            pnl = value - cost
            closed = data.get('closed', 0.0)
            strat_total_pnl = pnl + closed
            trade_count = data['count']
            strat_notes = "持仓市值=%.0f，成本=%.0f" % (value, cost)

            next_id_strat += 1
            conn.execute("""
                INSERT INTO portfolio_daily_strategy
                (id, date, strategy, position_cost, position_value, position_pnl,
                 closed_pnl, total_pnl, trade_count, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [next_id_strat, date_str, strategy, cost, value,
                  pnl, closed, strat_total_pnl, trade_count, strat_notes])
            count += 1

        print("✅ portfolio_daily_strategy %s: 新增 %d 条策略记录" % (date_str, count))
        return True

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='每日持仓快照更新')
    parser.add_argument('--date', type=str, help='目标日期 YYYYMMDD（默认今日）')
    parser.add_argument('--fix', action='store_true', help='强制覆盖已有记录')
    args = parser.parse_args()

    if args.date:
        target = datetime.strptime(args.date, '%Y%m%d').date()
    else:
        target = date.today()

    actual, is_holiday = get_target_date(target)

    print("=" * 50)
    print("目标日期: %s" % target)
    print("实际更新: %s" % actual + (" (节假日/周末沿用)" if is_holiday else ""))
    print("=" * 50)

    update_portfolio_daily(actual, force=args.fix)
    print()
    print("✅ 完成 %s 的持仓快照更新" % actual)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Stock Trade Skill - 量化交易执行
Auto-detects latest available trading date from daily_signals/daily_price tables
"""
import sys
sys.path.insert(0, '/Users/mawenhao/Desktop/code/股票策略')

import duckdb
from datetime import date
import subprocess
import os

DB_PATH = '/Users/mawenhao/Desktop/code/股票策略/data/Astock3.duckdb'
REPORT_DIR = '/Users/mawenhao/Desktop/code/obsidian/openclaw-skill/量化交易/日交易报告/'
INIT_CASH = 500000
TARGET_POSITION_RATIO = 0.85
PER_STOCK_MIN = 0.15
PER_STOCK_MAX = 0.30

conn = duckdb.connect(DB_PATH)

# Auto-detect latest available trading date from daily_signals
latest_signal_date = conn.execute("SELECT MAX(date) FROM daily_signals").fetchone()[0]
latest_price_date = conn.execute("SELECT MAX(trade_date) FROM dwd_daily_price").fetchone()[0]
TRADE_DATE = str(min(latest_signal_date, latest_price_date))

print(f"=== 量化交易执行 {TRADE_DATE} (自动检测) ===")
print()

# Step 1: Get positions
positions = conn.execute("""
    SELECT code, name, strategy, shares, buy_price 
    FROM positions WHERE status = 'holding'
""").fetchall()
print(f"持仓数量: {len(positions)}")

# Step 2: Check sell signals for each position
print("\n=== 卖出信号扫描 ===")
sells_to_execute = []
for p in positions:
    code, name, strategy, shares, buy_price = p
    sig = conn.execute(f"""
        SELECT signal_s1_full, signal_s1_half, signal_跌破多空线, signal_止损,
               signal_sell_b1, signal_sell_b2, signal_sell_blk, signal_sell_dl, 
               signal_sell_dz30, signal_sell_scb, signal_sell_blkB2
        FROM daily_signals WHERE code = '{code}' AND date = '{TRADE_DATE}'
    """).fetchone()
    
    if not sig:
        print(f"  {code} {name}: 无信号数据")
        continue
    
    # Universal sell signals (apply to ALL holdings regardless of strategy)
    if sig[0] or sig[1] or sig[2] or sig[3]:
        reasons = []
        if sig[0]: reasons.append("S1_FULL")
        if sig[1]: reasons.append("S1_HALF")
        if sig[2]: reasons.append("跌破多空线")
        if sig[3]: reasons.append("止损")
        sells_to_execute.append({
            'code': code, 'name': name, 'shares': shares, 'buy_price': buy_price,
            'sell_price': 0, 'reason': "+".join(reasons),
            'profit_loss': 0, 'profit_pct': 0
        })
        continue
    
    # Strategy-specific sell signals (only if holding has that strategy)
    strategy_sell = None
    if sig[4] and ('B1' in strategy or '天宫' in strategy):
        strategy_sell = "B1卖出"
    elif sig[5] and 'B2' in strategy:
        strategy_sell = "B2卖出"
    elif sig[6] and 'BLK' in strategy:
        strategy_sell = "BLK卖出"
    elif sig[7] and '地量' in strategy:
        strategy_sell = "地量卖出"
    elif sig[8] and '单针30' in strategy:
        strategy_sell = "单针30卖出"
    elif sig[9] and '沙尘暴' in strategy:
        strategy_sell = "SCB卖出"
    elif sig[10] and 'BLKB2' in strategy:
        strategy_sell = "BLKB2卖出"
    
    if strategy_sell:
        sells_to_execute.append({
            'code': code, 'name': name, 'shares': shares, 'buy_price': buy_price,
            'sell_price': 0, 'reason': strategy_sell,
            'profit_loss': 0, 'profit_pct': 0
        })

if not sells_to_execute:
    print("  无需卖出")

# Step 3: Execute sells
print("\n=== 执行卖出 ===")
total_sell_proceeds = 0
for s in sells_to_execute:
    if s['sell_price'] == 0:
        # Get current price for this stock
        price_row = conn.execute(f"SELECT close FROM dwd_daily_price WHERE ts_code = '{s['code']}' AND trade_date = '{TRADE_DATE}'").fetchone()
        s['sell_price'] = price_row[0] if price_row else s['buy_price']
        s['profit_pct'] = (s['sell_price'] - s['buy_price']) / s['buy_price'] * 100
        s['profit_loss'] = (s['sell_price'] - s['buy_price']) * s['shares'] - s['shares'] * s['buy_price'] * 0.0005
    
    conn.execute(f"""
        UPDATE positions 
        SET status = 'sold', 
            sell_date = '{TRADE_DATE}',
            sell_price = {s['sell_price']},
            sell_reason = '{s['reason']}',
            profit_loss = {s['profit_loss']}
        WHERE code = '{s['code']}' AND status = 'holding'
    """)
    sell_cost = s['shares'] * s['sell_price'] * 1.0005
    total_sell_proceeds += sell_cost
    print(f"  已卖出 {s['name']} {s['shares']}股 @{s['sell_price']:.2f} 盈亏:{s['profit_loss']:.0f}")

# Step 4: Recalculate position after sells
print("\n=== 仓位重算 ===")
current_positions = conn.execute("SELECT code, name, strategy, shares, buy_price FROM positions WHERE status = 'holding'").fetchall()
print(f"剩余持仓: {len(current_positions)}")

position_value = 0
for p in current_positions:
    price_row = conn.execute(f"SELECT close FROM dwd_daily_price WHERE ts_code = '{p[0]}' AND trade_date = '{TRADE_DATE}'").fetchone()
    price = price_row[0] if price_row else p[4]
    position_value += p[3] * price

position_cost = conn.execute("SELECT SUM(shares * buy_price * 1.0005) FROM positions WHERE status = 'holding'").fetchone()[0] or 0
closed_pnl = conn.execute("SELECT SUM(profit_loss) FROM positions WHERE status = 'sold'").fetchone()[0] or 0
available_cash = INIT_CASH - position_cost + closed_pnl + total_sell_proceeds
position_ratio = position_value / INIT_CASH * 100

print(f"持仓市值: {position_value:.0f}")
print(f"仓位比例: {position_ratio:.1f}%")
print(f"可用资金: {available_cash:.0f}")

# Step 5: Scan buy signals
print("\n=== 买入信号扫描 ===")
candidates = conn.execute(f"""
    SELECT code, name, 
           signal_buy_b1, signal_buy_b2, signal_buy_blk,
           signal_buy_dl, signal_buy_dz30, signal_buy_scb, signal_buy_blkB2,
           score_b1, score_b2, score_blk, score_dl, score_dz30, score_scb, score_blkB2,
           close, volume, change_pct
    FROM daily_signals 
    WHERE date = '{TRADE_DATE}'
    AND (signal_buy_b1 OR signal_buy_b2 OR signal_buy_blk 
         OR signal_buy_dl OR signal_buy_dz30 OR signal_buy_scb OR signal_buy_blkB2)
    LIMIT 50
""").fetchall()

buy_candidates = []
per_stock_min_amt = available_cash * PER_STOCK_MIN
per_stock_max_amt = available_cash * PER_STOCK_MAX

for c in candidates:
    code, name = c[0], c[1]
    price = c[16]
    volume = c[17]
    change_pct = c[18] if c[18] else 0
    strategies = []
    if c[2]: strategies.append('B1')
    if c[3]: strategies.append('B2')
    if c[4]: strategies.append('BLK')
    if c[5]: strategies.append('DL')
    if c[6]: strategies.append('DZ30')
    if c[7]: strategies.append('SCB')
    if c[8]: strategies.append('BLKB2')
    
    all_scores = [s for s in [c[9], c[10], c[11], c[12], c[13], c[14], c[15]] if s is not None]
    score = max(all_scores) if all_scores else 0
    strategy_count = len(strategies)
    combined_score = strategy_count * 10 + score
    
    held = conn.execute(f"SELECT COUNT(*) FROM positions WHERE code = '{code}' AND status = 'holding'").fetchone()[0]
    if held > 0:
        continue
    
    if change_pct < -1.5:
        continue
    
    max_shares = int(per_stock_max_amt / price)
    min_shares = int(per_stock_min_amt / price)
    
    buy_candidates.append({
        'code': code, 'name': name, 'price': price,
        'strategies': strategies, 'score': score,
        'strategy_count': strategy_count,
        'combined_score': combined_score,
        'volume': volume, 'change_pct': change_pct,
        'min_shares': min_shares, 'max_shares': max_shares,
        'min_amount': min_shares * price,
        'max_amount': max_shares * price
    })

buy_candidates.sort(key=lambda x: (x['combined_score'], x['volume']), reverse=True)

print(f"候选标的: {len(buy_candidates)} 只")
for i, b in enumerate(buy_candidates[:5]):
    print(f"  {i+1}. {b['name']}({b['code']}) {','.join(b['strategies'])} 评分:{b['combined_score']:.1f} 今日涨跌:{b['change_pct']:.2f}%")

# Step 6: Buy decision
print("\n=== 买入决策 ===")
should_buy = False
buy_analysis = ""
buy_stock = None

if position_ratio < TARGET_POSITION_RATIO * 100:
    should_buy = True
    buy_analysis += f"仓位{position_ratio:.1f}% < 目标仓位{TARGET_POSITION_RATIO*100:.0f}%，需要买入\n"
    
    if buy_candidates:
        best = None
        for b in buy_candidates:
            if b['strategy_count'] >= 2:
                best = b
                break
        
        if not best:
            for b in buy_candidates:
                if b['strategy_count'] == 1 and b['strategies'][0] == 'B1' and b['score'] > 12:
                    best = b
                    break
        
        if not best and buy_candidates:
            best = buy_candidates[0]
        
        if best:
            buy_stock = best
            buy_analysis += f"选择{best['name']}({best['code']})，触发{','.join(best['strategies'])}策略\n"
            buy_analysis += f"综合得分{best['combined_score']:.1f}(={best['strategy_count']}×10+{best['score']:.1f})\n"
            buy_analysis += f"今日涨跌:{best['change_pct']:.2f}%\n"
            buy_analysis += f"建议买入{best['min_shares']}-{best['max_shares']}股 ({best['min_amount']:.0f}-{best['max_amount']:.0f}元)\n"
else:
    buy_analysis += f"仓位{position_ratio:.1f}% >= {TARGET_POSITION_RATIO*100:.0f}%目标仓位，保持不变\n"

print(buy_analysis)

# Step 7: Execute buy
buys_executed = []
if should_buy and buy_stock:
    shares_to_buy = buy_stock['min_shares']
    buy_amt = shares_to_buy * buy_stock['price']
    
    # Normalize strategy name: single signal = signal name, multiple = A+B+C sorted
    strat_parts = sorted(buy_stock['strategies'])
    normalized_strategy = '+'.join(strat_parts)
    next_id = conn.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM positions').fetchone()[0]
    buy_notes = f"仓位{position_ratio:.1f}% < 目标仓位{TARGET_POSITION_RATIO*100:.0f}%，需要买入\n选择{buy_stock['name']}({buy_stock['code']})，触发{normalized_strategy}策略\n综合得分{buy_stock['combined_score']:.1f}(={buy_stock['strategy_count']}×10+{buy_stock['score']:.1f})\n{buy_stock['strategies'][0]}评分{buy_stock['score']:.1f}，今日涨跌:{buy_stock['change_pct']:.2f}%\n建议买入{shares_to_buy}股@{buy_stock['price']:.2f}=¥{buy_amt:.0f}"
    conn.execute(f"""
        INSERT INTO positions (id, code, name, strategy, shares, buy_price, buy_date, status, notes, buy_change_pct)
        VALUES ({next_id}, '{buy_stock['code']}', '{buy_stock['name']}', 
                '{normalized_strategy}',
                {shares_to_buy}, {buy_stock['price']}, '{TRADE_DATE}', 'holding',
                '{buy_notes}', {buy_stock['change_pct']})
    """)
    buys_executed.append({
        'code': buy_stock['code'],
        'name': buy_stock['name'],
        'shares': shares_to_buy,
        'price': buy_stock['price'],
        'amount': buy_amt,
        'strategies': buy_stock['strategies']
    })
    print(f"已买入 {buy_stock['name']} {shares_to_buy}股 @{buy_stock['price']:.2f}")

# Step 8: Collect report data (before closing connection)
print("\n=== 收集报告数据 ===")
final_positions = conn.execute("SELECT code, name, strategy, shares, buy_price FROM positions WHERE status = 'holding'").fetchall()
final_value = 0
for p in final_positions:
    price_row = conn.execute(f"SELECT close FROM dwd_daily_price WHERE ts_code = '{p[0]}' AND trade_date = '{TRADE_DATE}'").fetchone()
    price = price_row[0] if price_row else p[4]
    final_value += p[3] * price

final_cost = conn.execute("SELECT SUM(shares * buy_price * 1.0005) FROM positions WHERE status = 'holding'").fetchone()[0] or 0
final_closed_pnl = conn.execute("SELECT SUM(profit_loss) FROM positions WHERE status = 'sold'").fetchone()[0] or 0
final_position_pnl = final_value - final_cost
total_pnl = final_position_pnl + final_closed_pnl
final_available = INIT_CASH - final_cost + final_closed_pnl
final_ratio = final_value / INIT_CASH * 100
total_value = final_value + final_available

portfolio_row = conn.execute(f"SELECT position_ratio, total_value FROM portfolio_daily WHERE date = '{TRADE_DATE}'").fetchone()
prev_ratio = float(portfolio_row[0]) if portfolio_row else 0.0
prev_total = float(portfolio_row[1]) if portfolio_row else float(INIT_CASH)

holding_details = []
for p in final_positions:
    price_row = conn.execute(f"SELECT close FROM dwd_daily_price WHERE ts_code = '{p[0]}' AND trade_date = '{TRADE_DATE}'").fetchone()
    price = price_row[0] if price_row else p[4]
    sig = conn.execute(f"SELECT signal_止损, signal_跌破多空线 FROM daily_signals WHERE code = '{p[0]}' AND date = '{TRADE_DATE}'").fetchone()
    stop_loss = sig[0] if sig else None
    below_dual = sig[1] if sig else None
    pnl_pct = (price - p[4]) / p[4] * 100
    holding_details.append({
        'code': p[0], 'name': p[1], 'strategy': p[2],
        'shares': p[3], 'buy_price': p[4], 'current_price': price,
        'pnl_pct': pnl_pct, 'stop_loss': stop_loss, 'below_dual': below_dual
    })

recent_sold = conn.execute(f"""
    SELECT code, name, strategy, buy_date, sell_date, shares, buy_price, sell_price, profit_loss
    FROM positions WHERE status = 'sold' ORDER BY sell_date DESC LIMIT 5
""").fetchall()

# Close DB before running update_portfolio_daily (avoids lock conflict)
conn.close()
print("数据库连接已关闭")

# Step 9: Update portfolio_daily
print("\n=== 更新每日持仓 ===")
result = subprocess.run([
    '/opt/anaconda3/bin/python3.11',
    '/Users/mawenhao/Desktop/code/股票策略/scripts/update_portfolio_daily.py',
    '--date', TRADE_DATE.replace('-', ''), '--fix'
], capture_output=True, text=True, cwd='/Users/mawenhao/Desktop/code/股票策略')
print(result.stdout[-500:] if result.stdout else "")
if result.returncode != 0:
    print(f"UPDATE PORTFOLIO ERR: {result.stderr[-500:]}")

# Step 10: Generate and write report
print("\n=== 生成报告 ===")
report = f"""# 📊 量化交易报告 {TRADE_DATE}

## 💰 资金状况

| 指标 | 数值 |
|------|------|
| 初始资金 | {INIT_CASH:,.0f} |
| 当前持仓市值 | {final_value:,.0f} |
| 可用资金 | {final_available:,.0f} |
| 账户总资产 | {total_value:,.0f} |
| 持仓比例 | {final_ratio:.1f}% |
| 今日涨跌 | {final_ratio - prev_ratio:.1f}% |
| 持仓盈亏 | {final_position_pnl:,.0f} |
| 已平仓盈亏 | {final_closed_pnl:,.0f} |
| 总盈亏 | {total_pnl:,.0f} |

## 💡 买入决策分析

{buy_analysis}

"""

if buys_executed:
    report += "## 📈 今日买入\n\n"
    for b in buys_executed:
        report += f"- **{b['name']}({b['code']})** {b['shares']}股 @{b['price']:.2f} ({','.join(b['strategies'])}策略)\n"
else:
    report += "## 📈 今日买入\n\n无买入\n"

if sells_to_execute:
    report += "\n## 📉 今日卖出\n\n"
    for s in sells_to_execute:
        report += f"- **{s['name']}({s['code']})** {s['shares']}股 @{s['sell_price']:.2f} 原因:{s['reason']} 盈亏:{s['profit_pct']:.2f}%\n"
else:
    report += "\n## 📉 今日卖出\n\n无卖出\n"

report += f"""
## 📋 持仓明细 ({len(holding_details)}只)

| 股票 | 策略 | 持股数 | 成本 | 现价 | 盈亏% | 止损 | 跌破多空 |
|------|------|--------|------|------|-------|------|----------|
"""
for h in holding_details:
    stop_loss_icon = "⚠️" if h['stop_loss'] else "-"
    dual_icon = "⚠️" if h['below_dual'] else "-"
    report += f"| {h['name']} | {h['strategy']} | {h['shares']} | {h['buy_price']:.2f} | {h['current_price']:.2f} | {h['pnl_pct']:+.2f}% | {stop_loss_icon} | {dual_icon} |\n"

report += f"""
## 📜 已平仓交易 (最近5笔)

| 股票 | 买入日 | 卖出日 | 数量 | 成本 | 卖出价 | 盈亏 |
|------|--------|--------|------|------|--------|------|
"""
for s in recent_sold:
    report += f"| {s[1]} | {s[3]} | {s[4]} | {s[5]} | {s[6]:.2f} | {s[7]:.2f} | {s[8]:+.0f} |\n"

report += f"""
## ⚠️ 风险提示

- 止损线: -3%
- 多空线预警: 现价跌破多空线

---

*报告生成时间: {date.today().strftime('%Y-%m-%d %H:%M')}*
"""

os.makedirs(REPORT_DIR, exist_ok=True)
report_path = os.path.join(REPORT_DIR, f"{TRADE_DATE}.md")
with open(report_path, 'w') as f:
    f.write(report)

print(f"报告已生成: {report_path}")

# Step 11: Run trade audit
print("\n=== 交易审计 ===")
audit_result = subprocess.run([
    '/opt/anaconda3/bin/python3.11',
    '/Users/mawenhao/Desktop/code/股票策略/scripts/audit_trade.py',
    '--fix'
], capture_output=True, text=True, cwd='/Users/mawenhao/Desktop/code/股票策略')
audit_output = audit_result.stdout
if '【飞书发送】' in audit_output:
    start = audit_output.find('【飞书发送】\n') + 6
    end = audit_output.rfind('\n---')
    if end > start:
        feishu_content = audit_output[start:end].strip()
        print("审计发现问题，需要飞书通知")
print(f"审计输出末尾: {audit_output[-300:]}")
print(f"审计返回码: {audit_result.returncode}")

print("\n=== 量化交易执行完成 ===")
print(f"总资产: {total_value:,.0f} (持仓{final_ratio:.1f}%)")
print(f"总盈亏: {total_pnl:,.0f}")

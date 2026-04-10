import os
import sys

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify, request
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import akshare as ak

# Agent API路由
from dashboard.agent_api import agent_bp
from dashboard.data_update_api import data_update_bp

app = Flask(__name__)

# 注册蓝图
app.register_blueprint(agent_bp)
app.register_blueprint(data_update_bp)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'Astock3.duckdb')

def get_db():
    return duckdb.connect(DB_PATH)

def get_latest_trading_date():
    db = get_db()
    try:
        latest = db.execute("SELECT MAX(trade_date) FROM dwd_daily_price").fetchone()[0]
        if latest:
            return latest.strftime('%Y-%m-%d')
    finally:
        db.close()
    return datetime.now().strftime('%Y-%m-%d')

def code_to_ts_code(code: str) -> str:
    """转换股票代码为tushare格式"""
    code = str(code)
    if code.startswith('6'):
        return f"{code}.SH"
    else:
        return f"{code}.SZ"

def clean_df_for_json(df):
    for col in df.columns:
        if df[col].dtype == 'object' or str(df[col].dtype).startswith('datetime'):
            df[col] = df[col].apply(lambda x: None if pd.isna(x) else (x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else x))
        elif pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].replace({np.nan: None})
    return df

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/agent')
def agent():
    """多Agent股票分析页面"""
    return render_template('agent.html')

@app.route('/agent/history')
def agent_history():
    return render_template('history.html')

@app.route('/data-update')
def data_update():
    """数据更新页面"""
    return render_template('data_update.html')

@app.route('/api/positions')
def api_positions():
    db = get_db()
    try:
        # 获取排序参数，默认按buy_date DESC
        sort = request.args.get('sort', 'buy_date')
        order = request.args.get('order', 'desc')

        # 验证排序字段白名单
        allowed_sort_fields = {'buy_date', 'profit_pct', 'profit_loss', 'current_price', 'buy_price', 'name', 'code'}
        if sort not in allowed_sort_fields:
            sort = 'buy_date'

        # 验证排序方向
        order = order.upper() if order.upper() in ('ASC', 'DESC') else 'DESC'

        df = db.execute(f"""
            SELECT 
                id, code, name, strategy,
                signal_date, buy_date, shares, buy_price,
                buy_change_pct, buy_score_b1, buy_score_b2,
                current_price, profit_loss, profit_pct,
                stop_loss_pct, status, notes,
                ROUND(shares * buy_price * 0.9998, 2) as position_amount
            FROM positions 
            WHERE status = 'holding'
            ORDER BY {sort} {order}
        """).df()
        
        latest_date = get_latest_trading_date()
        if latest_date and not df.empty:
            # 优化：批量查询所有持仓股票的最新价格，避免 N+1 查询
            codes = df['code'].tolist()
            if codes:
                # 转换codes为tushare格式
                ts_codes = [code_to_ts_code(c) for c in codes]
                price_df = db.execute("""
                    SELECT ts_code, close 
                    FROM dwd_daily_price 
                    WHERE trade_date = ? AND ts_code IN (""" + ','.join(['?' for _ in ts_codes]) + """)
                """, [latest_date] + ts_codes).df()
                
                # 创建价格映射
                price_map = dict(zip(price_df['ts_code'], price_df['close']))
                
                for idx, row in df.iterrows():
                    ts_code = code_to_ts_code(row['code'])
                    current_price = price_map.get(ts_code)
                    if current_price is not None:
                        df.at[idx, 'current_price'] = current_price
                        if row['buy_price']:
                            profit_pct = (current_price - row['buy_price']) / row['buy_price'] * 100
                            profit_loss = (current_price - row['buy_price']) * row['shares']
                            df.at[idx, 'profit_pct'] = round(profit_pct, 2)
                            df.at[idx, 'profit_loss'] = round(profit_loss, 2)
        
        df = clean_df_for_json(df)
        positions = df.to_dict('records')
        
        # 查询历史交易总盈亏
        history_profit = db.execute("SELECT COALESCE(SUM(profit_loss), 0) FROM positions WHERE status = 'sold'").fetchone()[0]
        
        total_capital = 500000  # 总资金
        total_value = sum(p['current_price'] * p['shares'] if p['current_price'] else 0 for p in positions)
        total_cost = sum(p['buy_price'] * p['shares'] if p['buy_price'] else 0 for p in positions)
        holding_profit = total_value - total_cost  # 持仓盈亏
        total_profit = holding_profit + history_profit  # 总盈亏 = 持仓盈亏 + 历史盈亏
        available_cash = total_capital - total_value + total_profit  # 可用资金 = 50万 - 持仓市值 + 总盈亏
        
        return jsonify({
            'positions': positions,
            'summary': {
                'total_value': round(total_value, 2),
                'total_cost': round(total_cost, 2),
                'holding_profit': round(holding_profit, 2),
                'history_profit': round(history_profit, 2),
                'total_profit': round(total_profit, 2),
                'profit_pct': round(total_profit / total_cost * 100, 2) if total_cost > 0 else 0,
                'count': len(positions),
                'available_cash': round(available_cash, 2)
            }
        })
    finally:
        db.close()

@app.route('/api/history')
def api_history():
    db = get_db()
    try:
        df = db.execute("""
            SELECT 
                code, name, strategy,
                buy_date, buy_price, shares,
                sell_date, sell_price, sell_reason,
                profit_loss, profit_pct
            FROM positions 
            WHERE status = 'sold'
            ORDER BY sell_date DESC
        """).df()
        
        df = clean_df_for_json(df)
        history = df.to_dict('records')
        
        total_profit = sum(p['profit_loss'] if p['profit_loss'] else 0 for p in history)
        win_count = len([p for p in history if p['profit_loss'] and p['profit_loss'] > 0])
        loss_count = len([p for p in history if p['profit_loss'] and p['profit_loss'] < 0])
        
        return jsonify({
            'history': history,
            'summary': {
                'total_trades': len(history),
                'total_profit': round(total_profit, 2),
                'win_count': win_count,
                'loss_count': loss_count,
                'win_rate': round(win_count / len(history) * 100, 2) if len(history) > 0 else 0
            }
        })
    finally:
        db.close()

@app.route('/api/signals')
def api_signals():
    db = get_db()
    try:
        latest_date = db.execute("SELECT MAX(date) FROM daily_signals").fetchone()[0]
        
        if not latest_date:
            return jsonify({'signals': [], 'date': None})
        
        date_str = latest_date.strftime('%Y-%m-%d') if hasattr(latest_date, 'strftime') else str(latest_date)
        
        buy_signals = db.execute("""
            SELECT 
                code, name, close, change_pct,
                open, high, low, volume,
                score_b1, score_b2, 
                signal_buy_b1, signal_buy_b2,
                score_s1, signal_s1_full, signal_s1_half,
                signal_跌破多空线, signal_止损
            FROM daily_signals 
            WHERE date = ?
            AND (signal_buy_b1 = true OR signal_buy_b2 = true 
                 OR signal_s1_full = true OR signal_s1_half = true
                 OR signal_跌破多空线 = true OR signal_止损 = true)
            ORDER BY 
                CASE WHEN signal_buy_b1 = true THEN score_b1 
                     WHEN signal_buy_b2 = true THEN score_b2 
                     ELSE score_s1 END DESC
        """, [latest_date]).df()
        
        signals = buy_signals.to_dict('records')
        
        return jsonify({
            'signals': signals,
            'date': date_str,
            'buy_count': len([s for s in signals if s.get('signal_buy_b1') or s.get('signal_buy_b2')]),
            'sell_count': len([s for s in signals if s.get('signal_s1_full') or s.get('signal_s1_half')])
        })
    finally:
        db.close()

@app.route('/api/equity-curve')
def api_equity_curve():
    import signal
        
    def timeout_handler(signum, frame):
        raise TimeoutError("akshare API timeout")
    
    db = get_db()
    try:
        portfolio = db.execute("""
            SELECT 
                date,
                total_value,
                init_cash,
                position_ratio,
                closed_pnl,
                available_cash,
                (total_pnl - closed_pnl) AS position_pnl
            FROM portfolio_daily
            ORDER BY date
        """).fetchall()
        
        if not portfolio:
            dates = []
            for i in range(30):
                d = datetime.now() - timedelta(days=29-i)
                dates.append(d.strftime('%Y-%m-%d'))
            mock_values = [500000] * 30
            return jsonify({
                'dates': dates,
                'values': mock_values,
                'benchmark': [500000] * 30,
                'total_return': 0,
                'annotations': {
                    'peak': {'date': dates[0], 'value': 500000, 'return_pct': 0},
                    'trough': {'date': dates[-1], 'value': 500000},
                    'max_drawdown': {'date': None, 'pct': 0}
                }
            })
        
        dates = []
        values = []
        position_ratio_list = []
        closed_pnl_list = []
        available_cash_list = []
        position_pnl_list = []
        initial_value = 500000
        
        for p in portfolio:
            date, total_value, init_cash, position_ratio, closed_pnl, available_cash, position_pnl = p
            d_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
            dates.append(d_str)
            values.append(float(total_value) if total_value else 500000)
            position_ratio_list.append(round(float(position_ratio), 2) if position_ratio else 0)
            closed_pnl_list.append(round(float(closed_pnl), 2) if closed_pnl else 0)
            available_cash_list.append(round(float(available_cash), 2) if available_cash else 0)
            position_pnl_list.append(round(float(position_pnl), 2) if position_pnl else 0)
        
        # initial_value 从第一行的 init_cash 读取
        if portfolio and portfolio[0][2]:
            initial_value = float(portfolio[0][2])
        
        benchmark_values = []
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(10)
            index_df = ak.stock_zh_index_daily(symbol="sh000001")
            signal.alarm(0)
            index_df['date'] = pd.to_datetime(index_df['date']).dt.strftime('%Y-%m-%d')
            index_df = index_df[(index_df['date'] >= dates[0]) & (index_df['date'] <= dates[-1])]
            
            if not index_df.empty:
                first_close = index_df.iloc[0]['close']
                for d in dates:
                    idx_row = index_df[index_df['date'] == d]
                    if not idx_row.empty:
                        close = idx_row.iloc[0]['close']
                        benchmark_values.append(initial_value * close / first_close)
                    else:
                        benchmark_values.append(benchmark_values[-1] if benchmark_values else initial_value)
            else:
                benchmark_values = [initial_value] * len(dates)
        except TimeoutError:
            benchmark_values = [initial_value] * len(dates)
        except Exception as e:
            print(f"获取上证指数失败: {e}")
            benchmark_values = [initial_value] * len(dates)
        
        current_value = values[-1] if values else initial_value
        total_return = (current_value - initial_value) / initial_value * 100 if initial_value > 0 else 0
        
        # ========== 计算关键指标 ==========
        initial_value_const = 500000

        # 最大收益率和日期 (峰值)
        peak_value = max(values)
        peak_idx = values.index(peak_value)
        peak_date = dates[peak_idx]
        peak_return = (peak_value - initial_value_const) / initial_value_const * 100

        # 最低市值和日期 (谷值)
        trough_value = min(values)
        trough_idx = values.index(trough_value)
        trough_date = dates[trough_idx]

        # 最大回撤计算
        max_drawdown = 0
        max_drawdown_date = None
        peak_so_far = initial_value_const

        for i, (d, v) in enumerate(zip(dates, values)):
            if v > peak_so_far:
                peak_so_far = v
            drawdown = (peak_so_far - v) / peak_so_far * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_date = d

        return jsonify({
            'dates': dates,
            'values': [round(v, 2) for v in values],
            'benchmark': [round(v, 2) for v in benchmark_values],
            'total_return': round(total_return, 2),
            'annotations': {
                'peak': {
                    'date': peak_date,
                    'value': round(peak_value, 2),
                    'return_pct': round(peak_return, 2)
                },
                'trough': {
                    'date': trough_date,
                    'value': round(trough_value, 2)
                },
                'max_drawdown': {
                    'date': max_drawdown_date,
                    'pct': round(max_drawdown, 2)
                }
            },
            'position_ratio': position_ratio_list,
            'closed_pnl': closed_pnl_list,
            'available_cash': available_cash_list,
            'position_pnl': position_pnl_list
        })
    finally:
        db.close()

@app.route('/api/strategy-comparison')
def api_strategy_comparison():
    db = get_db()
    try:
        # 获取所有策略列表
        strategies = db.execute("SELECT DISTINCT strategy FROM portfolio_daily_strategy ORDER BY strategy").fetchall()
        
        if not strategies:
            return jsonify({'strategies': [], 'dates': [], 'curves': {}})
        
        # 获取所有日期
        dates = db.execute("SELECT DISTINCT date FROM portfolio_daily_strategy ORDER BY date").fetchall()
        date_strs = [d[0].strftime('%Y-%m-%d') if hasattr(d[0], 'strftime') else str(d[0]) for d in dates]
        
        # 初始资金
        initial_value = 500000
        
        # 获取每个策略的收益曲线
        curves = {}
        colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16']
        
        for i, (strategy_name,) in enumerate(strategies):
            strategy_data = db.execute("""
                SELECT date, total_pnl
                FROM portfolio_daily_strategy
                WHERE strategy = ?
                ORDER BY date
            """, [strategy_name]).fetchall()
            
            # 构建日期到总资产的映射
            asset_map = {}
            for sd in strategy_data:
                d = sd[0].strftime('%Y-%m-%d') if hasattr(sd[0], 'strftime') else str(sd[0])
                pnl = float(sd[1]) if sd[1] else 0
                asset_map[d] = initial_value + pnl
            
            # 按日期顺序生成曲线
            curve = []
            for d in date_strs:
                curve.append(asset_map.get(d, curve[-1] if curve else initial_value))
            
            curves[strategy_name] = {
                'data': [round(v, 2) for v in curve],
                'color': colors[i % len(colors)]
            }
        
        return jsonify({
            'strategies': [s[0] for s in strategies],
            'dates': date_strs,
            'curves': curves,
            'initial_value': initial_value
        })
    finally:
        db.close()

@app.route('/api/stats')
def api_stats():
    db = get_db()
    try:
        holding_count = db.execute("SELECT COUNT(*) FROM positions WHERE status = 'holding'").fetchone()[0]
        sold_count = db.execute("SELECT COUNT(*) FROM positions WHERE status = 'sold'").fetchone()[0]
        
        latest_date = db.execute("SELECT MAX(date) FROM daily_signals").fetchone()[0]
        buy_signals_count = 0
        if latest_date:
            buy_signals_count = db.execute("""
                SELECT COUNT(*) FROM daily_signals 
                WHERE date = ? AND (signal_buy_b1 = true OR signal_buy_b2 = true)
            """, [latest_date]).fetchone()[0]
        
        return jsonify({
            'holding_count': holding_count,
            'sold_count': sold_count,
            'today_buy_signals': buy_signals_count,
            'latest_date': latest_date.strftime('%Y-%m-%d') if latest_date else None
        })
    finally:
        db.close()

@app.route('/api/multi-signal-resonance')
def api_multi_signal_resonance():
    """获取多信号共振股票"""
    date_str = request.args.get('date')
    if not date_str:
        # 默认前一天
        date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    db = get_db()
    try:
        result = db.execute("""
            SELECT code, name,
                   signal_buy_b1, signal_buy_b2, signal_buy_blk, signal_buy_dl,
                   signal_buy_dz30, signal_buy_scb, signal_buy_blkB2,
                   close, change_pct
            FROM daily_signals
            WHERE date = ?
            AND (CAST(signal_buy_b1 AS INT) + CAST(signal_buy_b2 AS INT) + 
                 CAST(signal_buy_blk AS INT) + CAST(signal_buy_dl AS INT) + 
                 CAST(signal_buy_dz30 AS INT) + CAST(signal_buy_scb AS INT) + 
                 CAST(signal_buy_blkB2 AS INT)) >= 2
            ORDER BY (CAST(signal_buy_b1 AS INT) + CAST(signal_buy_b2 AS INT) + 
                      CAST(signal_buy_blk AS INT) + CAST(signal_buy_dl AS INT) + 
                      CAST(signal_buy_dz30 AS INT) + CAST(signal_buy_scb AS INT) + 
                      CAST(signal_buy_blkB2 AS INT)) DESC,
                     close DESC
        """, [date_str]).fetchall()
        
        signal_names = ['B1', 'B2', 'BLK', 'DL', 'DZ30', 'SCB', 'BLKB2']
        data = []
        for row in result:
            signals = [signal_names[i] for i, v in enumerate(row[2:9]) if v]
            data.append({
                'code': row[0],
                'name': row[1],
                'signal_count': len(signals),
                'signals': signals,
                'close': float(row[9]) if row[9] else 0,
                'change_pct': float(row[10]) if row[10] else 0
            })
        
        return jsonify({
            'date': date_str,
            'stocks': data,
            'count': len(data)
        })
    finally:
        db.close()

@app.route('/api/multi-signal-trend')
def api_multi_signal_trend():
    """获取多信号共振趋势数据"""
    db = get_db()
    try:
        result = db.execute("""
            SELECT date,
                   SUM(CAST(signal_buy_b1 AS INT)) as b1_count,
                   SUM(CAST(signal_buy_b2 AS INT)) as b2_count,
                   SUM(CAST(signal_buy_blk AS INT)) as blk_count,
                   SUM(CAST(signal_buy_dl AS INT)) as dl_count,
                   SUM(CAST(signal_buy_dz30 AS INT)) as dz30_count,
                   SUM(CAST(signal_buy_scb AS INT)) as scb_count,
                   SUM(CAST(signal_buy_blkB2 AS INT)) as blkB2_count,
                   COUNT(*) as total_count
            FROM daily_signals
            WHERE (CAST(signal_buy_b1 AS INT) + CAST(signal_buy_b2 AS INT) + 
                   CAST(signal_buy_blk AS INT) + CAST(signal_buy_dl AS INT) + 
                   CAST(signal_buy_dz30 AS INT) + CAST(signal_buy_scb AS INT) + 
                   CAST(signal_buy_blkB2 AS INT)) >= 2
            GROUP BY date
            ORDER BY date
        """).fetchall()
        
        dates = []
        total_counts = []
        signal_data = {
            'B1': [], 'B2': [], 'BLK': [], 'DL': [], 'DZ30': [], 'SCB': [], 'BLKB2': []
        }
        
        for row in result:
            date_str = row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0])
            dates.append(date_str)
            total_counts.append(int(row[8]))
            signal_data['B1'].append(int(row[1]))
            signal_data['B2'].append(int(row[2]))
            signal_data['BLK'].append(int(row[3]))
            signal_data['DL'].append(int(row[4]))
            signal_data['DZ30'].append(int(row[5]))
            signal_data['SCB'].append(int(row[6]))
            signal_data['BLKB2'].append(int(row[7]))
        
        return jsonify({
            'dates': dates,
            'total_counts': total_counts,
            'signal_data': signal_data
        })
    finally:
        db.close()


@app.route('/multi-signal-resonance')
def multi_signal_resonance():
    """多策略共振页面"""
    db = get_db()
    try:
        dates = db.execute("SELECT DISTINCT date FROM daily_signals ORDER BY date DESC LIMIT 30").fetchall()
        date_options = [{'value': d[0].strftime('%Y-%m-%d'), 'label': d[0].strftime('%Y-%m-%d')} for d in dates]
    finally:
        db.close()
    
    default_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    return render_template('multi_signal_resonance.html', 
                        date_options=date_options, 
                        default_date=default_date)



if __name__ == '__main__':
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    print("启动Dashboard服务: http://localhost:5004")
    app.run(debug=True, port=5004, host='0.0.0.0')

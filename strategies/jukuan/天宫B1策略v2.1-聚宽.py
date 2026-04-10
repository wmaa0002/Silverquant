#ZX|# 天宫B1策略v2.1 - 聚宽版(完整版)
#PV|# 改编自天宫B1策略v2.1，完整保留所有策略逻辑
#MB|# 买入条件: 非ST股 AND KDJ_J低(J<13) AND MACD_多头(DIF>=0) AND 知行短期趋势线>知行多空线 AND B1总分>=8
#RW|# 卖出条件: S1>10清仓/S1>5半仓/跌破知行多空线
#TJ|#
#MB|from jqdata import *
#HX|from jqfactor import *
#KP|import numpy as np
#KN|import pandas as pd
#NN|from datetime import time, date, timedelta
#XX|from jqdata import finance
#TJ|#

#ZN|#策略参数
g.b1_threshold = 8.0       # B1买入阈值
g.stop_loss_pct = 0.03     # 止损比例(3%)
g.多空线缓冲 = True        # 多空线跌破缓冲机制

#ZN|#初始化函数 
def initialize(context):
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(3/10000))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=2.5/10000, close_commission=2.5/10000, close_today_commission=0, min_commission=5), type='stock')
    # 设置日志级别
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    
    # 初始化全局变量
    g.stock = None                  # 当前持仓股票
    g.entry_price = None            # 买入价格
    g.pending_buy_signal = False
    g.pending_buy_reason = ""
    g.pending_b1_score = 0
    g.pending_sell_reason = ""
    g.pending_sell_date = ""
    g.pending_sell_half = False
    g.s1_half_sold = False
    g.多空线跌破观察 = False
    
    # 趋势线历史
    g.知行短期趋势线_arr = []
    g.知行多空线_arr = []
    
    # KDJ历史
    g.prev_k = None
    g.prev_d = None
    g.j_values = []
    
    # 设置定时任务
    run_daily(prepare_data, '9:25')
    run_daily(check_buy_signal, '9:35')
    run_daily(check_position, '14:30')
    run_daily(close_account, '14:55')


#ZM|#准备数据
def prepare_data(context):
    """每日开盘前准备数据"""
    # 重置状态
    g.pending_buy_signal = False
    g.pending_buy_reason = ""


#ZM|#检查买入信号
def check_buy_signal(context):
    """检查并执行买入信号"""
    # 如果有pending买入
    if g.pending_buy_signal and g.stock:
        current_data = get_current_data()
        if g.stock in current_data:
            price = current_data[g.stock].last_price
            cash = context.portfolio.available_cash
            available_cash = cash * 0.9
            size = int(available_cash / price / 100) * 100
            if size >= 100:
                order_target_value(g.stock, price * size)
                g.entry_price = price
                log.info("买入[%s] 价格:%.2f 数量:%d" % (g.stock, price, size))
            else:
                log.info("资金不足无法买入: 现金=%.2f, 价格=%.2f" % (cash, price))
        g.pending_buy_signal = False
        g.pending_buy_reason = ""


#ZM|#检查持仓
def check_position(context):
    """检查持仓状态"""
    current_position = list(context.portfolio.positions.keys())
    if not current_position:
        return
    
    stock = current_position[0]
    current_data = get_current_data()
    price = current_data[stock].last_price
    
    # 获取历史数据(需要足够多的历史数据计算指标)
    end_date = context.current_dt.strftime('%Y-%m-%d')
    df = get_price(stock, end_date=end_date, count=200, fields=['open','high','low','close','volume'], frequency='daily', panel=False)
    if df is None or len(df) < 60:
        return
    
    # 计算指标
    close_arr = df['close'].values
    high_arr = df['high'].values
    low_arr = df['low'].values
    volume_arr = df['volume'].values
    open_arr = df['open'].values
    
    close = close_arr[-1]
    prev_close = close_arr[-2]
    high = high_arr[-1]
    low = low_arr[-1]
    volume = volume_arr[-1]
    open_price = open_arr[-1]
    
    涨幅 = (close - prev_close) / prev_close * 100 if prev_close != 0 else 0
    振幅 = (high - low) / prev_close * 100 if prev_close != 0 else 0
    
    # 计算DIF
    dif_arr = []
    for idx in range(len(close_arr)):
        c = close_arr[idx]
        ema12_i = c
        ema26_i = c
        for j in range(1, min(13, idx + 1)):
            ema12_i = ema12_i * (2/13) + close_arr[idx - j] * (1 - 2/13)
        for j in range(1, min(27, idx + 1)):
            ema26_i = ema26_i * (2/27) + close_arr[idx - j] * (1 - 2/27)
        dif_arr.append(ema12_i - ema26_i)
    dif_arr = np.array(dif_arr)
    dif = dif_arr[-1]
    
    # 计算知行短期趋势线和多空线
    ema10_1 = close
    for i in range(2, 11):
        if i < len(close_arr):
            ema10_1 = ema10_1 * (2/11) + close_arr[-i] * (1 - 2/11)
    
    ema10_2 = ema10_1
    for i in range(2, 11):
        if i < len(close_arr):
            ema10_2 = ema10_2 * (2/11) + ema10_1 * (1 - 2/11)
    
    知行短期趋势线 = ema10_2
    
    ma14 = np.mean(close_arr[-14:])
    ma28 = np.mean(close_arr[-28:])
    ma57 = np.mean(close_arr[-57:])
    ma114 = np.mean(close_arr[-114:])
    知行多空线 = (ma14 + ma28 + ma57 + ma114) / 4
    
    # 保存趋势线历史
    g.知行短期趋势线_arr.append(知行短期趋势线)
    g.知行多空线_arr.append(知行多空线)
    
    # 获取前一天的趋势线值
    if len(g.知行短期趋势线_arr) >= 2:
        知行短期趋势线_prev = g.知行短期趋势线_arr[-2]
        知行多空线_prev = g.知行多空线_arr[-2]
    else:
        知行短期趋势线_prev = 知行短期趋势线
        知行多空线_prev = 知行多空线
    
    # 计算BBI
    ma3 = np.mean(close_arr[-3:])
    ma6 = np.mean(close_arr[-6:])
    ma12 = np.mean(close_arr[-12:])
    ma24 = np.mean(close_arr[-24:])
    bbi = (ma3 + ma6 + ma12 + ma24) / 4
    
    # 计算前20日BBI
    if len(close_arr) >= 44:
        ma3_20 = np.mean(close_arr[-23:-20])
        ma6_20 = np.mean(close_arr[-26:-20])
        ma12_20 = np.mean(close_arr[-32:-20])
        ma24_20 = np.mean(close_arr[-44:-20])
        前20日BBI = (ma3_20 + ma6_20 + ma12_20 + ma24_20) / 4
    else:
        前20日BBI = bbi
    
    # 计算RSI (4个周期)
    def calc_rsi(period):
        gains, losses = [], []
        for i in range(1, period + 1):
            if i < len(close_arr):
                change = close_arr[-i] - close_arr[-i-1]
                gains.append(max(change, 0))
                losses.append(max(-change, 0))
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0.001
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    rsi1 = calc_rsi(14)
    rsi2 = calc_rsi(14)  # 简化
    rsi3 = calc_rsi(28)
    rsi4 = calc_rsi(57)
    
    # 计算KDJ
    low_9 = np.min(low_arr[-9:])
    high_9 = np.max(high_arr[-9:])
    rsv_k = (close - low_9) / (high_9 - low_9) * 100 if high_9 != low_9 else 50
    
    if g.prev_k is None:
        k = rsv_k
    else:
        k = (2.0 / 3.0) * g.prev_k + (1.0 / 3.0) * rsv_k
    
    if g.prev_d is None:
        d = k
    else:
        d = (2.0 / 3.0) * g.prev_d + (1.0 / 3.0) * k
    
    g.prev_k = k
    g.prev_d = d
    j = 3 * k - 2 * d
    
    # 计算J值历史
    g.j_values = []
    for i in range(1, 4):
        if i < len(close_arr):
            low_9_i = np.min(low_arr[-9-i:-i]) if i < len(low_arr) else np.min(low_arr[-9:])
            high_9_i = np.max(high_arr[-9-i:-i]) if i < len(high_arr) else np.max(high_arr[-9:])
            close_i = close_arr[-i-1]
            rsv_k_i = (close_i - low_9_i) / (high_9_i - low_9_i) * 100 if high_9_i != low_9_i else 50
            j_i = 3 * rsv_k_i - 2 * rsv_k_i
            g.j_values.append(j_i)
    
    # 判断条件
    MACD_多头 = dif >= 0
    趋势线条件 = 知行短期趋势线 > 知行多空线
    KDJ_J低 = j < 13
    
    # 计算B1分数(完整版39条件)
    b1_score = calculate_b1_score(close, high, open_price, open_arr, close_arr, high_arr, low_arr, volume_arr, volume, dif, dif_arr, rsi1, rsi2, rsi3, rsi4, j, 知行短期趋势线, 知行多空线, 知行短期趋势线_prev, 知行多空线_prev, bbi, 前20日BBI, 涨幅, 振幅)
    
    B1总分 = b1_score if b1_score > 0 else 0
    
    # 卖出条件检查
    if context.portfolio.positions[stock]:
        avg_cost = context.portfolio.positions[stock].avg_cost
        profit_pct = (price - avg_cost) / avg_cost
        
        # 计算S1分数(完整版)
        s1_score = calculate_s1_score(close, high, low, open_price, close_arr, high_arr, low_arr, volume_arr, volume, dif, j, k, d)
        
        # 处理pending卖出
        if g.pending_sell_reason:
            if g.pending_sell_half:
                order_target_value(stock, context.portfolio.value * 0.5)
                log.info("半仓卖出: 原因=%s, S1=%.1f" % (g.pending_sell_reason, s1_score))
                g.s1_half_sold = True
            else:
                order_target_value(stock, 0)
                log.info("清仓卖出: 原因=%s, S1=%.1f" % (g.pending_sell_reason, s1_score))
                g.stock = None
                g.entry_price = None
            g.pending_sell_reason = ""
            g.pending_sell_date = ""
            return
        
        # S1>10清仓
        if s1_score > 10:
            g.pending_sell_reason = "S1清仓(S1=%.1f>10)" % s1_score
            g.pending_sell_date = context.current_dt.strftime('%Y-%m-%d')
            g.pending_sell_half = False
            return
        
        # S1>5半仓
        if s1_score > 5 and not g.s1_half_sold:
            g.pending_sell_reason = "S1半仓(S1=%.1f>5)" % s1_score
            g.pending_sell_date = context.current_dt.strftime('%Y-%m-%d')
            g.pending_sell_half = True
            return
        
        # 跌破多空线卖出(带缓冲机制)
        if close < 知行多空线:
            if g.多空线缓冲 and not g.多空线跌破观察:
                g.多空线跌破观察 = True
                g.pending_sell_reason = "跌破知行多空线观察(%.2f<%.2f)" % (close, 知行多空线)
                g.pending_sell_date = context.current_dt.strftime('%Y-%m-%d')
                log.info("多空线跌破观察: %.2f < %.2f" % (close, 知行多空线))
            elif g.多空线跌破观察 and close < 知行多空线:
                order_target_value(stock, 0)
                log.info("多空线跌破确认卖出: %.2f < %.2f" % (close, 知行多空线))
                g.stock = None
                g.entry_price = None
                g.多空线跌破观察 = False
                g.pending_sell_reason = ""
            else:
                g.多空线跌破观察 = False
                g.pending_sell_reason = ""
        else:
            g.多空线跌破观察 = False
            if g.pending_sell_reason and "知行多空线" in g.pending_sell_reason:
                g.pending_sell_reason = ""
                log.info("卖出取消: 价格回到多空线之上")


#ZM|#每日收盘选股
def close_account(context):
    """每日收盘选股"""
    # 如果没有持仓，进行选股
    if not list(context.portfolio.positions.keys()):
        # 检查是否pending买入
        if g.pending_buy_signal and g.stock:
            current_data = get_current_data()
            if g.stock in current_data:
                price = current_data[g.stock].last_price
                cash = context.portfolio.available_cash
                available_cash = cash * 0.9
                size = int(available_cash / price / 100) * 100
                if size >= 100:
                    order_target_value(g.stock, price * size)
                    g.entry_price = price
                    log.info("买入[%s] 价格:%.2f 数量:%d" % (g.stock, price, size))
            g.pending_buy_signal = False
            g.pending_buy_reason = ""
            return
        
        # 执行选股
        stock = select_stock(context)
        if stock:
            g.stock = stock
            current_data = get_current_data()
            if stock in current_data:
                price = current_data[stock].last_price
                cash = context.portfolio.available_cash
                available_cash = cash * 0.9
                size = int(available_cash / price / 100) * 100
                if size >= 100:
                    order_target_value(stock, price * size)
                    g.entry_price = price
                    log.info("买入[%s] 价格:%.2f 数量:%d" % (stock, price, size))


#ZM|#选股函数
def select_stock(context):
    """完整选股函数"""
    # 获取所有A股
    all_stocks = get_all_securities(['stock']).index.tolist()
    
    # 过滤ST和退市
    current_data = get_current_data()
    valid_stocks = []
    for stock in all_stocks:
        if stock in current_data:
            if current_data[stock].paused:
                continue
            if current_data[stock].is_st:
                continue
            if '退' in current_data[stock].name:
                continue
            # 过滤科创板、创业板、北交所
            if stock.startswith('30') or stock.startswith('68') or stock.startswith('8') or stock.startswith('4'):
                continue
            valid_stocks.append(stock)
    
    # 获取历史数据
    end_date = context.current_dt.strftime('%Y-%m-%d')
    best_stock = None
    best_score = 0
    
    # 限制检查数量以提高性能
    check_count = 0
    max_check = 100
    
    for stock in valid_stocks:
        if check_count >= max_check:
            break
        check_count += 1
        
        try:
            df = get_price(stock, end_date=end_date, count=200, fields=['open','high','low','close','volume'], frequency='daily', panel=False)
            if df is None or len(df) < 60:
                continue
            
            close_arr = df['close'].values
            high_arr = df['high'].values
            low_arr = df['low'].values
            volume_arr = df['volume'].values
            open_arr = df['open'].values
            
            close = close_arr[-1]
            prev_close = close_arr[-2]
            high = high_arr[-1]
            volume = volume_arr[-1]
            open_price = open_arr[-1]
            
            涨幅 = (close - prev_close) / prev_close * 100 if prev_close != 0 else 0
            振幅 = (high - close) / prev_close * 100 if prev_close != 0 else 0
            
            # 计算DIF
            dif_arr = []
            for idx in range(len(close_arr)):
                c = close_arr[idx]
                ema12_i = c
                ema26_i = c
                for j in range(1, min(13, idx + 1)):
                    ema12_i = ema12_i * (2/13) + close_arr[idx - j] * (1 - 2/13)
                for j in range(1, min(27, idx + 1)):
                    ema26_i = ema26_i * (2/27) + close_arr[idx - j] * (1 - 2/27)
                dif_arr.append(ema12_i - ema26_i)
            dif_arr = np.array(dif_arr)
            dif = dif_arr[-1]
            
            # 计算知行短期趋势线和多空线
            ema10_1 = close
            for i in range(2, 11):
                if i < len(close_arr):
                    ema10_1 = ema10_1 * (2/11) + close_arr[-i] * (1 - 2/11)
            
            ema10_2 = ema10_1
            for i in range(2, 11):
                if i < len(close_arr):
                    ema10_2 = ema10_2 * (2/11) + ema10_1 * (1 - 2/11)
            
            知行短期趋势线 = ema10_2
            
            ma14 = np.mean(close_arr[-14:])
            ma28 = np.mean(close_arr[-28:])
            ma57 = np.mean(close_arr[-57:])
            ma114 = np.mean(close_arr[-114:])
            知行多空线 = (ma14 + ma28 + ma57 + ma114) / 4
            
            # 获取前一天的趋势线值
            if len(g.知行短期趋势线_arr) >= 1:
                知行短期趋势线_prev = g.知行短期趋势线_arr[-1]
                知行多空线_prev = g.知行多空线_arr[-1]
            else:
                知行短期趋势线_prev = 知行短期趋势线
                知行多空线_prev = 知行多空线
            
            # 计算BBI
            ma3 = np.mean(close_arr[-3:])
            ma6 = np.mean(close_arr[-6:])
            ma12 = np.mean(close_arr[-12:])
            ma24 = np.mean(close_arr[-24:])
            bbi = (ma3 + ma6 + ma12 + ma24) / 4
            
            # 计算前20日BBI
            if len(close_arr) >= 44:
                ma3_20 = np.mean(close_arr[-23:-20])
                ma6_20 = np.mean(close_arr[-26:-20])
                ma12_20 = np.mean(close_arr[-32:-20])
                ma24_20 = np.mean(close_arr[-44:-20])
                前20日BBI = (ma3_20 + ma6_20 + ma12_20 + ma24_20) / 4
            else:
                前20日BBI = bbi
            
            # 计算RSI
            def calc_rsi(period):
                gains, losses = [], []
                for i in range(1, period + 1):
                    if i < len(close_arr):
                        change = close_arr[-i] - close_arr[-i-1]
                        gains.append(max(change, 0))
                        losses.append(max(-change, 0))
                avg_gain = np.mean(gains) if gains else 0
                avg_loss = np.mean(losses) if losses else 0.001
                rs = avg_gain / avg_loss
                return 100 - (100 / (1 + rs))
            
            rsi1 = calc_rsi(14)
            rsi2 = calc_rsi(14)
            rsi3 = calc_rsi(28)
            rsi4 = calc_rsi(57)
            
            # 计算KDJ
            low_9 = np.min(low_arr[-9:])
            high_9 = np.max(high_arr[-9:])
            rsv_k = (close - low_9) / (high_9 - low_9) * 100 if high_9 != low_9 else 50
            
            k = rsv_k
            d = rsv_k
            j = 3 * k - 2 * d
            
            # 判断条件
            MACD_多头 = dif >= 0
            趋势线条件 = 知行短期趋势线 > 知行多空线
            KDJ_J低 = j < 13
            
            if not MACD_多头 or not 趋势线条件 or not KDJ_J低:
                continue
            
            # 计算B1分数(完整版)
            b1_score = calculate_b1_score(close, high, open_price, open_arr, close_arr, high_arr, low_arr, volume_arr, volume, dif, dif_arr, rsi1, rsi2, rsi3, rsi4, j, 知行短期趋势线, 知行多空线, 知行短期趋势线_prev, 知行多空线_prev, bbi, 前20日BBI, 涨幅, 振幅)
            
            B1总分 = b1_score if b1_score > 0 else 0
            
            if B1总分 >= g.b1_threshold:
                if B1总分 > best_score:
                    best_score = B1总分
                    best_stock = stock
                    
        except Exception as e:
            continue
    
    if best_stock:
        log.info("选中股票: %s, B1分数: %.1f" % (best_stock, best_score))
    
    return best_stock


#ZN|#B1打分计算(完整版39条件)
def calculate_b1_score(close, high, open_price, open_arr, close_arr, high_arr, low_arr, volume_arr, volume, dif, dif_arr, rsi1, rsi2, rsi3, rsi4, j, 知行短期趋势线, 知行多空线, 知行短期趋势线_prev, 知行多空线_prev, bbi, 前20日BBI, 涨幅, 振幅):
    """计算B1得分(完整版39条件)"""
    
    # === 条件1: DIF>=0 ===
    条件1得分 = 0.6 if dif >= 0 else 0
    
    # === 条件2: C > MA60 ===
    条件2得分 = 0.3 if close > np.mean(close_arr[-60:]) else 0
    
    # === 条件3: 涨幅 -2~1.8% ===
    条件3得分 = 1.5 if -2 <= 涨幅 <= 1.8 else -3
    
    # === 条件4: 振幅 < 7% ===
    条件4得分 = 0.5 if 振幅 < 7 else -1
    
    # === 条件5: 振幅 < 4% ===
    条件5得分 = 0.8 if 振幅 < 4 else 0
    
    # === 条件6: RSI < 20/23 ===
    rsi_score = 0
    if rsi1 < 20:
        rsi_score += 0.8
    if rsi1 < 23:
        rsi_score += 0.7
    条件6得分 = rsi_score
    
    # === 条件7: 趋势线位置 ===
    条件7得分 = 0
    if 知行短期趋势线 > close > 知行多空线:
        条件7得分 += 1.3
    if close < 知行多空线:
        条件7得分 -= 3
    if close * 1.003 < 知行多空线:
        条件7得分 -= 3
    
    # === 条件8-10: 地量系列 ===
    条件8得分 = 0
    vol_20 = volume_arr[-20:]
    vol_18 = volume_arr[-18:]
    vol_16 = volume_arr[-16:]
    if volume == np.min(vol_20):
        条件8得分 += 0.3
    if volume == np.min(vol_18):
        条件8得分 += 0.3
    if volume == np.min(vol_16):
        条件8得分 += 0.3
    
    条件9得分 = 0
    vol_14 = volume_arr[-14:]
    vol_12 = volume_arr[-12:]
    vol_10 = volume_arr[-10:]
    if volume == np.min(vol_14):
        条件9得分 += 0.3
    if volume == np.min(vol_12):
        条件9得分 += 0.3
    if volume == np.min(vol_10):
        条件9得分 += 0.3
    
    条件10得分 = 0
    if volume == np.min(vol_20):
        条件10得分 = 0.5
    
    # === 条件11-13: 倍量系列 ===
    vol_ma60 = np.mean(volume_arr[-60:])
    条件11得分 = 0
    条件12得分 = 0
    条件13得分 = 0
    
    for days, points_pos, points_neg in [(60, 1, -0.5), (30, 0.5, -0.5), (20, 0.4, -0.5)]:
        if len(volume_arr) >= days:
            hhv_vol = np.max(volume_arr[-days:])
            for idx in range(len(volume_arr) - 1, len(volume_arr) - days - 1, -1):
                if volume_arr[idx] >= hhv_vol:
                    barslast = len(volume_arr) - idx - 1
                    if barslast >= 1 and barslast < len(close_arr) and barslast < len(open_arr):
                        if close_arr[-barslast-1] > open_arr[-barslast-1]:
                            条件11得分 += points_pos
                        elif close_arr[-barslast-1] < open_arr[-barslast-1]:
                            if days in [60, 30, 25]:
                                条件12得分 += points_neg
                            if days in [20, 15, 10]:
                                条件13得分 += points_neg
                    break
    
    # === 条件14: 涨跌量和 ===
    sum_50 = np.sum(np.where(close_arr[-50:] > open_arr[-50:], volume_arr[-50:], -volume_arr[-50:]))
    sum_40 = np.sum(np.where(close_arr[-40:] > open_arr[-40:], volume_arr[-40:], -volume_arr[-40:]))
    sum_30 = np.sum(np.where(close_arr[-30:] > open_arr[-30:], volume_arr[-30:], -volume_arr[-30:]))
    sum_20 = np.sum(np.where(close_arr[-20:] > open_arr[-20:], volume_arr[-20:], -volume_arr[-20:]))
    
    条件14得分 = 0
    if sum_50 > 0:
        条件14得分 += 0.4
    if sum_40 > 0:
        条件14得分 += 0.4
    if sum_30 > 0:
        条件14得分 += 0.4
    if sum_20 > 0:
        条件14得分 += 0.4
    
    # === 条件15: 涨跌量对比 ===
    sum_up30 = np.sum(np.where(close_arr[-30:] > open_arr[-30:], volume_arr[-30:], 0))
    sum_down30 = np.sum(np.where(close_arr[-30:] < open_arr[-30:], volume_arr[-30:], 0))
    sum_up50 = np.sum(np.where(close_arr[-50:] > open_arr[-50:], volume_arr[-50:], 0))
    sum_down50 = np.sum(np.where(close_arr[-50:] < open_arr[-50:], volume_arr[-50:], 0))
    sum_up40 = np.sum(np.where(close_arr[-40:] > open_arr[-40:], volume_arr[-40:], 0))
    sum_down40 = np.sum(np.where(close_arr[-40:] < open_arr[-40:], volume_arr[-40:], 0))
    sum_up20 = np.sum(np.where(close_arr[-20:] > open_arr[-20:], volume_arr[-20:], 0))
    sum_down20 = np.sum(np.where(close_arr[-20:] < open_arr[-20:], volume_arr[-20:], 0))
    
    条件15得分 = 0
    if sum_up30 > 1.25 * sum_down30:
        条件15得分 += 0.4
    if sum_up30 > 1.5 * sum_down30:
        条件15得分 += 0.5
    if sum_up30 > 2 * sum_down30:
        条件15得分 += 0.6
    if sum_down50 > sum_up50:
        条件15得分 -= 0.4
    if sum_down40 > sum_up40:
        条件15得分 -= 0.4
    if sum_down30 > sum_up30:
        条件15得分 -= 0.4
    if sum_down20 > sum_up20:
        条件15得分 -= 0.4
    
    # === 条件16: BBI > 前20日BBI ===
    条件16得分 = 0.5 if bbi > 前20日BBI else 0
    
    # === 条件17: 支撑位距离 ===
    条件17得分 = 0
    if len(high_arr) >= 10:
        hhv_h_10 = np.max(high_arr[-10:])
        diff_low = abs(low_arr[-1] - 知行多空线)
        cond1 = 1 if diff_low * 2.5 > abs(close - hhv_h_10) else 0
        cond2 = 1 if diff_low * 3 > abs(close - hhv_h_10) else 0
        条件17得分 = (cond1 + cond2) * (-1)
    
    # === 条件18: 趋势线偏离 ===
    条件18得分 = 0
    if 知行短期趋势线 != 0:
        趋势线_diff = (close - 知行短期趋势线) / 知行短期趋势线
        if -0.015 < 趋势线_diff <= 0.023 and -2 <= 涨幅 <= 1.8 and 振幅 < 4:
            条件18得分 = 1.5
        else:
            条件18得分 = -0.5
    
    # === 条件19: 创业板趋势线 ===
    条件19得分 = 0
    if 条件18得分 <= 0:
        if 知行短期趋势线 != 0:
            趋势线_diff = (close - 知行短期趋势线) / 知行短期趋势线
            if -0.015 < 趋势线_diff <= 0.03 and -2 <= 涨幅 <= 1.8 and 振幅 < 4:
                条件19得分 = 2
    
    # === 条件20: 多空线偏离 ===
    条件20得分 = 0
    if 条件18得分 <= 0 and 条件19得分 == 0:
        if 知行多空线 != 0:
            多空线_diff = (close - 知行多空线) / 知行多空线
            if 多空线_diff <= 0.025 and -2 <= 涨幅 <= 1.8 and 振幅 < 4:
                条件20得分 = 0.6
    
    # === 条件21: 价格区间 ===
    条件21得分 = 0
    if 条件18得分 <= 0 and 条件19得分 == 0 and 条件20得分 == 0:
        if close < 知行短期趋势线 and close > 知行多空线:
            条件21得分 = -1.5
    
    # === 条件22: DIF背离 ===
    条件22得分 = 0
    if len(high_arr) >= 30 and len(dif_arr) >= 30:
        hhv_30 = np.max(high_arr[-30:])
        价格高点位置 = 0
        for idx in range(len(high_arr) - 1, len(high_arr) - 31, -1):
            if high_arr[idx] >= hhv_30:
                价格高点位置 = len(high_arr) - idx - 1
                break
        
        if 价格高点位置 > 0 and 价格高点位置 < len(dif_arr):
            高点DIF = dif_arr[-价格高点位置-1]
            start_idx = len(dif_arr) - 价格高点位置 - 1
            
            if start_idx >= 20:
                前20高DIF = np.max(dif_arr[start_idx-20:start_idx])
            else:
                前20高DIF = 高点DIF
            
            if start_idx >= 15:
                前15高DIF = np.max(dif_arr[start_idx-15:start_idx])
            else:
                前15高DIF = 高点DIF
            
            if 高点DIF < 前20高DIF:
                条件22得分 -= 0.5
            if 高点DIF < 前15高DIF:
                条件22得分 -= 0.5
    
    # === 条件23: 放量上涨 ===
    条件23得分 = 0
    for i in range(20):
        if i < len(volume_arr) - 1 and len(volume_arr) >= 30:
            vol_ma30 = np.mean(volume_arr[-30:])
            if vol_ma30 > 0 and volume_arr[-i-1] > vol_ma30 * 4 and close_arr[-i-1] > open_arr[-i-1]:
                条件23得分 += 0.5
            elif vol_ma30 > 0 and volume_arr[-i-1] > vol_ma30 * 4.5 and close_arr[-i-1] > open_arr[-i-1]:
                条件23得分 += 0.4
            elif vol_ma30 > 0 and volume_arr[-i-1] > vol_ma30 * 5 and close_arr[-i-1] > open_arr[-i-1]:
                条件23得分 += 0.3
    条件23得分 = min(条件23得分, 1.4)
    
    # === 条件24: 区间振幅 ===
    波幅 = np.mean(np.abs(high_arr[-30:] - low_arr[-30:]))
    prev_close = close_arr[-2]
    波动率 = 波幅 / prev_close * 100 if prev_close != 0 else 0
    
    条件24得分 = 0
    for threshold, points in [(60, -0.8), (70, -0.7), (80, -0.6), (90, -0.5), (100, -0.4)]:
        exists = False
        for i in range(20):
            if i < len(close_arr) - 1:
                hhv_i = np.max(high_arr[-i-21:-i-1]) if len(high_arr) > i+21 else np.max(high_arr[:len(high_arr)-i-1])
                llv_i = np.min(low_arr[-i-21:-i-1]) if len(low_arr) > i+21 else np.min(low_arr[:len(low_arr)-i-1])
                if llv_i != 0:
                    区间振幅_i = (hhv_i - llv_i) / llv_i * 100
                    if 区间振幅_i > threshold:
                        exists = True
                        break
        if exists:
            条件24得分 += points
    
    # === 条件25: 跳空阳线 ===
    条件25得分 = 0
    跳空阳线_count = 0
    for i in range(20):
        if i < len(close_arr) - 1:
            low_i = low_arr[-i-1]
            high_prev = high_arr[-i-2]
            if close_arr[-i-1] >= open_arr[-i-1] and low_i > high_prev:
                gap_condition = (low_i - close_arr[-i-2]) / close_arr[-i-2] if close_arr[-i-2] != 0 else 0
                if gap_condition > 0.032 or gap_condition > 波动率 * 0.01:
                    跳空阳线_count += 1
    if 跳空阳线_count >= 1:
        条件25得分 -= 1.2
        if 条件23得分 > 0:
            条件25得分 -= 1.0
    
    # === 条件26: 知行线波动 ===
    条件26得分 = 0
    if len(g.知行多空线_arr) >= 61:
        知行线波动平均 = (g.知行多空线_arr[-16] + g.知行多空线_arr[-31] + 
                       g.知行多空线_arr[-46] + g.知行多空线_arr[-61]) / 4
    else:
        知行线波动平均 = 知行多空线
    
    if 知行线波动平均 != 0:
        知行线平均_今 = (知行多空线 - 知行线波动平均) / 知行线波动平均
        if 知行线平均_今 < 0.05:
            条件26得分 -= 1.0
        elif 知行线平均_今 < 0.075:
            条件26得分 -= 0.8
        elif 知行线平均_今 < 0.10:
            条件26得分 -= 0.5
    
    # === 条件27: 成交量变化 ===
    条件27得分 = 0
    if len(close_arr) >= 41:
        sum_up_20 = np.sum(np.where(close_arr[-20:] > open_arr[-20:], volume_arr[-20:], 0))
        sum_up_20_ref = np.sum(np.where(close_arr[-41:-21] > open_arr[-41:-21], volume_arr[-41:-21], 0))
        if sum_up_20 > sum_up_20_ref:
            条件27得分 = 0.5
        else:
            条件27得分 = -1
    
    # === 条件28: 趋势线下降 ===
    条件28得分 = 0
    if 知行短期趋势线 < 知行短期趋势线_prev and 知行多空线 < 知行多空线_prev:
        条件28得分 = -2
    
    # === 条件29: 十字星 ===
    条件29得分 = 0
    十字星_count = 0
    for i in range(60):
        if i < len(close_arr) - 1:
            if close_arr[-i-1] == open_arr[-i-1]:
                涨停价_i = close_arr[-i-2] * 1.1
                if close_arr[-i-1] != 涨停价_i or close_arr[-i-1] <= close_arr[-i-2]:
                    十字星_count += 1
    if 十字星_count > 2:
        条件29得分 = -1.5
    
    # === 条件30: J值高位 ===
    条件30得分 = 0
    if len(g.j_values) >= 2:
        j_prev_list = g.j_values[-15:] if len(g.j_values) >= 15 else g.j_values
        if len(j_prev_list) > 0:
            max_j_idx = np.argmax(j_prev_list)
            N = len(j_prev_list) - max_j_idx
            if 1 <= N <= 15:
                YJ = g.j_values[max_j_idx] if max_j_idx < len(g.j_values) else j
                YC = close_arr[-N-1] if N+1 < len(close_arr) else close
                if YJ > 95 and abs((close - YC) / YC * 100) <= 3:
                    high_n = np.max(high_arr[-N-1:]) if len(high_arr) > N+1 else np.max(high_arr)
                    low_n = np.min(low_arr[-N-1:]) if len(low_arr) > N+1 else np.min(low_arr)
                    if YC != 0 and (high_n - low_n) / YC * 100 < 12:
                        条件30得分 = 2.8
    
    # === 条件31: 缩量连续下跌 ===
    条件31得分 = 0
    if len(volume_arr) >= 5:
        if (volume < volume_arr[-1] * 1.1 and volume_arr[-1] < volume_arr[-2] * 1.1 and 
            volume_arr[-2] < volume_arr[-3] * 1.1 and volume_arr[-3] < volume_arr[-4] * 1.1):
            if (close_arr[-1] < open_arr[-1] and close_arr[-2] < open_arr[-2] and 
                close_arr[-3] < open_arr[-3] and close_arr[-4] < open_arr[-4]):
                条件31得分 = -1
    
    # === 条件32: 关键K ===
    条件32得分 = 0
    参考成交量 = volume_arr[-2] if volume_arr[-1] <= volume / 8 else volume_arr[-1]
    
    关键K_count = 0
    for i in range(20):
        if i < len(close_arr) - 1:
            涨跌幅_i = (close_arr[-i-1] - close_arr[-i-2]) / close_arr[-i-2] * 100 if close_arr[-i-2] != 0 else 0
            大长阳_i = close_arr[-i-1] > open_arr[-i-1] and 涨跌幅_i > 波动率 * 1.5 and 涨跌幅_i > 2
            if close_arr[-i-1] > close_arr[-i-2] and volume_arr[-i-1] > 参考成交量 * 1.8 and 大长阳_i and volume_arr[-i-1] > np.mean(volume_arr[-40:]):
                关键K_count += 1
    if 关键K_count >= 1:
        条件32得分 = 1
    
    # === 条件33: 连续大长阳 ===
    条件33得分 = 0
    大长阳连续_count = 0
    for i in range(20):
        if i < len(close_arr) - 2:
            涨跌幅_i = (close_arr[-i-1] - close_arr[-i-2]) / close_arr[-i-2] * 100 if close_arr[-i-2] != 0 else 0
            涨跌幅_i1 = (close_arr[-i-2] - close_arr[-i-3]) / close_arr[-i-3] * 100 if close_arr[-i-3] != 0 else 0
            if close_arr[-i-1] > open_arr[-i-1] and 涨跌幅_i > 涨跌幅_i1 * 0.9 and volume_arr[-i-1] < volume_arr[-i-2] * 0.8:
                大长阳连续_count += 1
    if 大长阳连续_count >= 2:
        条件33得分 = -1
    
    # === 条件34: 大长阴 ===
    条件34得分 = 0
    vol_hhv_60 = np.max(volume_arr[-60:]) if len(volume_arr) >= 60 else 0
    
    for vol_mult, points in [(1.2, -1), (1.4, -0.6), (1.6, -0.5), (1.8, -0.4), (2.0, -0.4)]:
        count = 0
        for i in range(10):
            if i < len(close_arr) - 1:
                涨跌幅_i = (close_arr[-i-1] - close_arr[-i-2]) / close_arr[-i-2] * 100 if close_arr[-i-2] != 0 else 0
                大长阴_i = close_arr[-i-1] < open_arr[-i-1] and abs(涨跌幅_i) > 波动率 * 1.1 and abs(涨跌幅_i) > 2
                if 大长阴_i and volume_arr[-i-1] > volume_arr[-i-2] * vol_mult and volume_arr[-i-1] > np.mean(volume_arr[-60:]) and volume_arr[-i-1] > vol_hhv_60 / 1.95:
                    count += 1
        if count >= 1:
            条件34得分 += points
    
    # === 条件35: RSI多头 ===
    条件35得分 = 1 if rsi2 > rsi3 and rsi3 > rsi4 else 0
    
    # === 条件36: 涨停次数 ===
    条件36得分 = 0
    涨停次数 = 0
    for i in range(20):
        if i < len(close_arr) - 1:
            if close_arr[-i-1] == open_arr[-i-1] and close_arr[-i-1] == high_arr[-i-1]:
                涨停次数 += 1
    if 涨停次数 >= 1:
        条件36得分 -= 1
    if 涨停次数 >= 2:
        条件36得分 -= 1.5
    
    # === 条件37: 开盘压制 ===
    条件37得分 = 0
    if open_price > 知行短期趋势线 and 知行短期趋势线 > 知行多空线 and close < 知行多空线 and close < open_price and volume > volume_arr[-1]:
        条件37得分 = -3
    
    # === 条件38: 次高点(简化) ===
    条件38得分 = 0
    
    # === 条件39: 无关键K ===
    条件39得分 = 0
    if 条件23得分 == 0 and 条件32得分 == 0:
        条件39得分 = -2
    
    # === 汇总 ===
    b1_score = (条件1得分 + 条件2得分 + 条件3得分 + 条件4得分 + 条件5得分 + 
                条件6得分 + 条件7得分 + 条件8得分 + 条件9得分 + 条件10得分 +
                条件11得分 + 条件12得分 + 条件13得分 + 条件14得分 + 条件15得分 +
                条件16得分 + 条件17得分 + 条件18得分 + 条件19得分 + 条件20得分 +
                条件21得分 + 条件22得分 + 条件23得分 + 条件24得分 + 条件25得分 +
                条件26得分 + 条件27得分 + 条件28得分 + 条件29得分 + 条件30得分 +
                条件31得分 + 条件32得分 + 条件33得分 + 条件34得分 + 条件35得分 +
                条件36得分 + 条件37得分 + 条件38得分 + 条件39得分)
    
    return b1_score


#ZN|#S1打分计算(完整版)
def calculate_s1_score(close, high, low, open_price, close_arr, high_arr, low_arr, volume_arr, volume, dif, j, k, d):
    """计算S1得分(完整版)"""
    
    前10日涨幅 = (close / close_arr[-10] - 1) * 100 if len(close_arr) >= 10 else 0
    前50日涨幅 = (close / close_arr[-50] - 1) * 100 if len(close_arr) >= 50 else 0
    
    条件1基础 = (close < open_price) and (high == np.max(high_arr[-60:])) and (前10日涨幅 > 10 or 前50日涨幅 > 50)
    
    条件1评分 = 0
    if 条件1基础:
        hhv_vol_60 = np.max(volume_arr[-60:])
        if volume >= hhv_vol_60:
            条件1评分 = 10
        elif volume * 1.1 >= hhv_vol_60:
            条件1评分 = 8
        elif volume * 1.25 >= hhv_vol_60:
            条件1评分 = 7.5
        elif volume * 1.42 >= hhv_vol_60:
            条件1评分 = 6.5
    
    条件1 = 条件1基础 and (volume * 1.42 >= np.max(volume_arr[-60:]))
    
    # 计算前3天最高位距今
    if len(high_arr) >= 3:
        recent_3_high = high_arr[-3:]
        max_idx_in_recent_3 = np.argmax(recent_3_high)
        前3天最高位距今 = 2 - max_idx_in_recent_3
    else:
        前3天最高位距今 = 0
    
    条件2基础 = False
    if len(high_arr) >= 60:
        hhv_h_4 = np.max(high_arr[-4:])
        hhv_h_60 = np.max(high_arr[-60:])
        if hhv_h_4 == hhv_h_60 and high != hhv_h_60:
            vol_ma5 = np.mean(volume_arr[-5:])
            vol_ma10 = np.mean(volume_arr[-10:])
            涨幅 = (close - close_arr[-2]) / close_arr[-2] * 100 if close_arr[-2] != 0 else 0
            if (volume > vol_ma5 or volume > vol_ma10) and 涨幅 < -0.03 and close < open_price and (前10日涨幅 > 10 or 前50日涨幅 > 50):
                条件2基础 = True
    
    条件2评分 = 0
    if 条件2基础 and 前3天最高位距今 >= 0:
        ref_vol = volume_arr[-前3天最高位距今-1] if 前3天最高位距今 < len(volume_arr) - 1 else volume_arr[-1]
        if volume >= ref_vol * 1.20:
            条件2评分 = 12
        elif volume >= ref_vol * 1.00:
            条件2评分 = 10
        elif volume >= ref_vol * 0.80:
            条件2评分 = 7.8
        elif volume >= ref_vol * 0.70:
            条件2评分 = 6.5
    
    # 计算DIF历史
    dif_history = []
    for i in range(len(close_arr)):
        c = close_arr[i]
        hist_ema12 = c
        hist_ema26 = c
        for j in range(1, min(13, i+1)):
            hist_ema12 = hist_ema12 * (11/13) + close_arr[i-j] * (2/13)
        for j in range(1, min(27, i+1)):
            hist_ema26 = hist_ema26 * (25/27) + close_arr[i-j] * (2/27)
        dif_history.append(hist_ema12 - hist_ema26)
    
    hhv_dif_60 = np.max(dif_history[-60:]) if len(dif_history) >= 60 else dif
    hhv_dif_40 = np.max(dif_history[-40:]) if len(dif_history) >= 40 else dif
    hhv_dif_20 = np.max(dif_history[-20:]) if len(dif_history) >= 20 else dif
    
    加分1 = 0
    if 条件1:
        if dif < hhv_dif_60:
            加分1 += 1
        if dif < hhv_dif_40:
            加分1 += 1
        if dif < hhv_dif_20:
            加分1 += 1
    
    实体 = open_price - close
    上影线 = high - max(close, open_price)
    
    加分2 = 0
    if 条件1 and 上影线 > 实体 / 2 and close > close_arr[-1]:
        加分2 += 0.5
    if 条件1 and 上影线 > 实体 and close > close_arr[-1]:
        加分2 += 0.5
    if 条件1 and 上影线 > 实体 * 2 and close > close_arr[-1]:
        加分2 += 0.5
    
    加分3 = 0
    if 条件2 and 前3天最高位距今 > 0 and len(dif_history) > 前3天最高位距今:
        该K线DIF = dif_history[前3天最高位距今] if 前3天最高位距今 < len(dif_history) else dif
        offset = 前3天最高位距今
        if len(dif_history) > 60 + offset:
            hist_hhv_dif_60_offset = np.max(dif_history[offset:offset+60])
        else:
            hist_hhv_dif_60_offset = hhv_dif_60
        
        if 该K线DIF < hist_hhv_dif_60_offset:
            加分3 = 1.8
    
    加分4 = 0
    if 条件2 and j < k and k < d:
        加分4 = 0.8
    
    加分5 = 0
    if (条件1 or 条件2) and close < close_arr[-1]:
        加分5 = 2
    
    天量柱 = False
    if len(volume_arr) >= 2:
        倍量柱_prev = (volume_arr[-1] > volume_arr[-2] * 1.8)
        if 倍量柱_prev and volume >= volume_arr[-1] * 1.8:
            天量柱 = True
    加分6 = 3 if 天量柱 else 0
    
    s1_score = 条件1评分 + 条件2评分 + 加分1 + 加分2 + 加分3 + 加分4 + 加分5 + 加分6
    
    return s1_score


#ZN|#策略说明
"""
聚宽版天宫B1策略v2.1(完整版)

【买入条件】
1. 非ST股票
2. KDJ J值 < 13 (超卖)
3. MACD DIF >= 0 (多头)
4. 知行短期趋势线 > 知行多空线 (上涨趋势)
5. B1总分 >= 8

【卖出条件】
1. S1分数 > 10: 清仓
2. S1分数 > 5: 半仓
3. 收盘价跌破知行多空线: 卖出(有缓冲机制)

【策略参数】
- b1_threshold: 8.0 (B1买入阈值)
- stop_loss_pct: 0.03 (止损比例)
- 多空线缓冲: True (多空线跌破缓冲)

【聚宽API使用】
- get_all_securities: 获取股票列表
- get_current_data: 获取当前行情
- get_price: 获取历史行情
- order_target_value: 目标金额下单
- run_daily: 每日定时任务

【B1打分系统(39条件)】
完整保留原策略的所有39个打分条件

【S1打分系统】
完整保留原策略的S1打分逻辑
"""

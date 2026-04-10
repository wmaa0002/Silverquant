import backtrader as bt
import pandas as pd
import numpy as np
import akshare as ak
import duckdb
from datetime import datetime
import csv
import os

class TiangongB1Strategy(bt.Strategy):
    params = (
        ('b1_threshold', 8.0),  
        ('stop_loss_pct', 0.03),  # 止损3%
        ('多空线缓冲', True),  # 多空线跌破缓冲机制
    )
    
    def __init__(self):
        self.close = self.data.close
        self.open = self.data.open
        self.high = self.data.high
        self.low = self.data.low
        self.volume = self.data.volume
        
        self.entry_price = None
        self.s1_half_sold = False
        self.多空线跌破观察 = False  # 多空线跌破观察期
        self.order = None
        
        self.pending_buy_signal = False
        self.pending_buy_reason = ""
        self.pending_b1_score = 0  # 保存买入信号产生时的B1分数
        self.pending_sell_reason = ""
        self.pending_sell_half = False
        
        self.st_days = self.data._name.startswith('ST') or '*ST' in self.data._name
        
        self.知行短期趋势线_arr = []
        self.知行多空线_arr = []
        
        # 添加交易记录列表
        self.trade_records = []
        self.current_b1_score = 0
        self.current_j_value = 0
        self.current_dif_value = 0
        
        self.prev_k = None
        self.prev_d = None
    
    def calculate_b1_score(self, close, high, open_price_scalar, open_arr, close_arr, high_arr, low_arr, volume_arr, volume, dif, dif_arr, rsi1, rsi2, rsi3, rsi4, j, 知行短期趋势线, 知行多空线, 知行短期趋势线_prev, 知行多空线_prev, bbi, 前20日BBI, 涨幅, 振幅, debug=False):
        
        close_price = close
        open_p = open_price_scalar
        
        条件1得分 = 0.6 if dif >= 0 else 0
        条件2得分 = 0.3 if close > np.mean(close_arr[-60:]) else 0
        条件3得分 = 1.5 if -2 <= 涨幅 <= 1.8 else -3
        条件4得分 = 0.5 if 振幅 < 7 else -1
        条件5得分 = 0.8 if 振幅 < 4 else 0
        
        rsi_score = 0
        if rsi1 < 20:
            rsi_score += 0.8
        if rsi1 < 23:
            rsi_score += 0.7
        条件6得分 = rsi_score
        
        条件7得分 = 0
        if 知行短期趋势线 > close > 知行多空线:
            条件7得分 += 1.3
        if close < 知行多空线:
            条件7得分 -= 3
        if close * 1.003 < 知行多空线:
            条件7得分 -= 3
        
        # 通达信公式: 一字涨停:=(O=C)AND(C=H)AND(C=涨停价)
        # 涨停价: ST股5%, 300/688/科创板20%, 其它10%
        prev_close = close_arr[-1] if len(close_arr) > 1 else close
        stock_code = self.data._name if hasattr(self.data, '_name') else '300486'
        if stock_code.startswith('300') or stock_code.startswith('688') or stock_code.startswith('301'):
            涨停价 = prev_close * 1.2
        else:
            涨停价 = prev_close * 1.1
        
        # 判断当前是否一字涨停
        一字涨停 = (open_p == close) and (close == high) and (close >= 涨停价 * 0.99)
        
        # 通达信条件8/9: IF(V=LLV(IF(一字涨停,10000000,V),N),得分,0)
        # 需要遍历历史每一天，判断是否一字涨停，是则用10000000替代
        def get_vol_with_yiziting(vol_arr, days):
            result = []
            for i in range(days):
                if i < len(vol_arr):
                    # 获取该天的O、H、C
                    idx = len(vol_arr) - days + i
                    if idx >= 0 and idx < len(open_arr) and idx < len(high_arr) and idx < len(close_arr):
                        o = open_arr[idx]
                        h = high_arr[idx]
                        c = close_arr[idx]
                        # 判断是否一字涨停
                        if (o == c) and (c == h) and (c >= 涨停价 * 0.99):
                            result.append(10000000)
                        else:
                            result.append(vol_arr[idx])
                    else:
                        result.append(vol_arr[idx])
            return np.array(result)
        
        vol_30_adj = get_vol_with_yiziting(volume_arr, 30)
        vol_26_adj = get_vol_with_yiziting(volume_arr, 26)
        vol_24_adj = get_vol_with_yiziting(volume_arr, 24)
        vol_22_adj = get_vol_with_yiziting(volume_arr, 22)
        vol_20_adj = get_vol_with_yiziting(volume_arr, 20)
        vol_18_adj = get_vol_with_yiziting(volume_arr, 18)
        vol_16_adj = get_vol_with_yiziting(volume_arr, 16)
        vol_14_adj = get_vol_with_yiziting(volume_arr, 14)
        vol_12_adj = get_vol_with_yiziting(volume_arr, 12)
        vol_10_adj = get_vol_with_yiziting(volume_arr, 10)
        
        条件8得分 = 0
        if volume == np.min(vol_30_adj):
            条件8得分 += 0.3
        if volume == np.min(vol_26_adj):
            条件8得分 += 0.3
        if volume == np.min(vol_24_adj):
            条件8得分 += 0.3
        if volume == np.min(vol_22_adj):
            条件8得分 += 0.3
        if volume == np.min(vol_20_adj):
            条件8得分 += 0.3
        
        条件9得分 = 0
        if volume == np.min(vol_18_adj):
            条件9得分 += 0.3
        if volume == np.min(vol_16_adj):
            条件9得分 += 0.3
        if volume == np.min(vol_14_adj):
            条件9得分 += 0.3
        if volume == np.min(vol_12_adj):
            条件9得分 += 0.3
        if volume == np.min(vol_10_adj):
            条件9得分 += 0.3
        
        条件10得分 = 0
        # 通达信条件10: IF(V=LLV(V,20) OR V=LLV(V,19) OR V=LLV(V,18),0.5,0)
        # 注意：条件10没有使用一字涨停处理，与条件8、9不同
        vol_20_adj = volume_arr[-20:]
        vol_19_adj = volume_arr[-19:]
        vol_18_adj = volume_arr[-18:]
        if volume == np.min(vol_20_adj) or volume == np.min(vol_19_adj) or volume == np.min(vol_18_adj):
            条件10得分 = 0.5
        
        vol_ma60 = np.mean(volume_arr[-60:])
        条件11得分 = 0
        for days, points in [(60, 1), (30, 0.5), (20, 0.4), (10, 0.3)]:
            if len(volume_arr) >= days:
                hhv_vol_days = np.max(volume_arr[-days:])
                barslast_hhv = 0
                for idx in range(len(volume_arr) - 1, len(volume_arr) - days - 1, -1):
                    if volume_arr[idx] >= hhv_vol_days:
                        barslast_hhv = len(volume_arr) - idx - 1
                        break
                if barslast_hhv >= 1 and barslast_hhv < len(close_arr) and barslast_hhv < len(open_arr):
                    if close_arr[-barslast_hhv-1] > open_arr[-barslast_hhv-1]:
                        条件11得分 += points
        
        条件12得分 = 0
        for days, points in [(60, -0.5), (30, -0.5), (25, -0.5)]:
            if len(volume_arr) >= days:
                hhv_vol_days = np.max(volume_arr[-days:])
                barslast_hhv = 0
                for idx in range(len(volume_arr) - 1, len(volume_arr) - days - 1, -1):
                    if volume_arr[idx] >= hhv_vol_days:
                        barslast_hhv = len(volume_arr) - idx - 1
                        break
                if barslast_hhv >= 1 and barslast_hhv < len(close_arr) and barslast_hhv < len(open_arr):
                    if close_arr[-barslast_hhv-1] < open_arr[-barslast_hhv-1]:
                        条件12得分 += points
        
        条件13得分 = 0
        for days, points in [(20, -0.6), (15, -0.7), (10, -0.8)]:
            if len(volume_arr) >= days:
                hhv_vol_days = np.max(volume_arr[-days:])
                barslast_hhv = 0
                for idx in range(len(volume_arr) - 1, len(volume_arr) - days - 1, -1):
                    if volume_arr[idx] >= hhv_vol_days:
                        barslast_hhv = len(volume_arr) - idx - 1
                        break
                if barslast_hhv >= 1 and barslast_hhv < len(close_arr) and barslast_hhv < len(open_arr):
                    if close_arr[-barslast_hhv-1] < open_arr[-barslast_hhv-1]:
                        条件13得分 += points
        
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
        
        条件16得分 = 0.5 if bbi > 前20日BBI else 0
        
        条件17得分 = 0
        if len(high_arr) >= 10:
            hhv_h_10 = np.max(high_arr[-10:])
            diff_low = abs(low_arr[-1] - 知行多空线)
            cond1 = 1 if diff_low * 2.5 > abs(close - hhv_h_10) else 0
            cond2 = 1 if diff_low * 3 > abs(close - hhv_h_10) else 0
            条件17得分 = (cond1 + cond2) * (-1)
        
        条件18得分 = 0
        if 知行短期趋势线 != 0:
            趋势线_diff = (close - 知行短期趋势线) / 知行短期趋势线
            if -0.015 < 趋势线_diff <= 0.023 and -2 <= 涨幅 <= 1.8 and 振幅 < 4:
                条件18得分 = 1.5
            else:
                条件18得分 = -0.5
        
        条件19得分 = 0
        if 条件18得分 <= 0:
            is_not_60_or_00 = not (str(self.data._name).startswith('60') or str(self.data._name).startswith('00'))
            if is_not_60_or_00:
                if 知行短期趋势线 != 0:
                    趋势线_diff = (close - 知行短期趋势线) / 知行短期趋势线
                    if -0.015 < 趋势线_diff <= 0.03 and -2 <= 涨幅 <= 1.8 and 振幅 < 4:
                        条件19得分 = 2
        
        条件20得分 = 0
        if 条件18得分 <= 0 and 条件19得分 == 0:
            if 知行多空线 != 0:
                多空线_diff = (close - 知行多空线) / 知行多空线
                if 多空线_diff <= 0.025 and -2 <= 涨幅 <= 1.8 and 振幅 < 4:
                    条件20得分 = 0.6
        
        条件21得分 = 0
        # 通达信: C < 知行短期趋势线 AND C > 知行多空线 时扣分
        if 条件18得分 <= 0 and 条件19得分 == 0 and 条件20得分 == 0:
            if close < 知行短期趋势线 and close > 知行多空线:
                条件21得分 = -1.5
        
        价格高点位置 = 0
        if len(high_arr) >= 30:
            hhv_30 = np.max(high_arr[-30:])
            for idx in range(len(high_arr) - 1, len(high_arr) - 31, -1):
                if high_arr[idx] >= hhv_30:
                    价格高点位置 = len(high_arr) - idx - 1
                    break
        
        条件22得分 = 0
        if 价格高点位置 > 0 and 价格高点位置 < len(dif_arr):
            高点DIF = dif_arr[-价格高点位置-1]
            start_idx = len(dif_arr) - 价格高点位置 - 1
            end_idx_20 = len(dif_arr) - 价格高点位置 - 21
            end_idx_15 = len(dif_arr) - 价格高点位置 - 16
            
            if end_idx_20 >= 0 and end_idx_20 < start_idx:
                前20高DIF = np.max(dif_arr[end_idx_20:start_idx])
            else:
                前20高DIF = 高点DIF
                
            if end_idx_15 >= 0 and end_idx_15 < start_idx:
                前15高DIF = np.max(dif_arr[end_idx_15:start_idx])
            else:
                前15高DIF = 高点DIF
            
            if 高点DIF < 前20高DIF:
                条件22得分 -= 0.5
            if 高点DIF < 前15高DIF:
                条件22得分 -= 0.5
        
        条件23得分 = 0
        vol_ma30_arr = []
        for i in range(30):
            if i < len(volume_arr):
                vol_ma30_i = np.mean(volume_arr[-(i+30):-i]) if i < len(volume_arr) - 30 else np.mean(volume_arr[:])
                vol_ma30_arr.append(vol_ma30_i)
        vol_ma30_current = np.mean(volume_arr[-30:])
        
        # 通达信 EXIST(VOL>MA(VOL,30)*4 AND C>O,20) - 检查过去20天内是否存在
        for i in range(20):
            if i < len(volume_arr) - 1:
                vol_ma30_i = np.mean(volume_arr[-(i+30):-i]) if i < len(volume_arr) - 30 else np.mean(volume_arr[:-(i+1)])
                if vol_ma30_i > 0 and volume_arr[-i-1] > vol_ma30_i * 4 and close_arr[-i-1] > open_arr[-i-1]:
                    条件23得分 += 0.5
                elif vol_ma30_i > 0 and volume_arr[-i-1] > vol_ma30_i * 4.5 and close_arr[-i-1] > open_arr[-i-1]:
                    条件23得分 += 0.4
                elif vol_ma30_i > 0 and volume_arr[-i-1] > vol_ma30_i * 5 and close_arr[-i-1] > open_arr[-i-1]:
                    条件23得分 += 0.3
                elif vol_ma30_i > 0 and volume_arr[-i-1] > vol_ma30_i * 5.5 and close_arr[-i-1] > open_arr[-i-1]:
                    条件23得分 += 0.2
        条件23得分 = min(条件23得分, 1.4)
        
        条件24得分 = 0
        # 检查过去20天内是否存在区间振幅>60
        exists_60 = False
        for i in range(20):
            if i < len(close_arr) - 1:
                hhv_i = np.max(high_arr[-i-21:-i-1]) if len(high_arr) > i+21 else np.max(high_arr[:len(high_arr)-i-1])
                llv_i = np.min(low_arr[-i-21:-i-1]) if len(low_arr) > i+21 else np.min(low_arr[:len(low_arr)-i-1])
                if llv_i != 0:
                    区间振幅_i = (hhv_i - llv_i) / llv_i * 100
                    if 区间振幅_i > 60:
                        exists_60 = True
                        break
        if exists_60:
            条件24得分 -= 0.8
        
        # 检查过去20天内是否存在区间振幅>70
        exists_70 = False
        for i in range(20):
            if i < len(close_arr) - 1:
                hhv_i = np.max(high_arr[-i-21:-i-1]) if len(high_arr) > i+21 else np.max(high_arr[:len(high_arr)-i-1])
                llv_i = np.min(low_arr[-i-21:-i-1]) if len(low_arr) > i+21 else np.min(low_arr[:len(low_arr)-i-1])
                if llv_i != 0:
                    区间振幅_i = (hhv_i - llv_i) / llv_i * 100
                    if 区间振幅_i > 70:
                        exists_70 = True
                        break
        if exists_70:
            条件24得分 -= 0.7
            
        # 检查过去20天内是否存在区间振幅>80
        exists_80 = False
        for i in range(20):
            if i < len(close_arr) - 1:
                hhv_i = np.max(high_arr[-i-21:-i-1]) if len(high_arr) > i+21 else np.max(high_arr[:len(high_arr)-i-1])
                llv_i = np.min(low_arr[-i-21:-i-1]) if len(low_arr) > i+21 else np.min(low_arr[:len(low_arr)-i-1])
                if llv_i != 0:
                    区间振幅_i = (hhv_i - llv_i) / llv_i * 100
                    if 区间振幅_i > 80:
                        exists_80 = True
                        break
        if exists_80:
            条件24得分 -= 0.6
            
        # 检查过去20天内是否存在区间振幅>90
        exists_90 = False
        for i in range(20):
            if i < len(close_arr) - 1:
                hhv_i = np.max(high_arr[-i-21:-i-1]) if len(high_arr) > i+21 else np.max(high_arr[:len(high_arr)-i-1])
                llv_i = np.min(low_arr[-i-21:-i-1]) if len(low_arr) > i+21 else np.min(low_arr[:len(low_arr)-i-1])
                if llv_i != 0:
                    区间振幅_i = (hhv_i - llv_i) / llv_i * 100
                    if 区间振幅_i > 90:
                        exists_90 = True
                        break
        if exists_90:
            条件24得分 -= 0.5
            
        # 检查过去20天内是否存在区间振幅>100
        exists_100 = False
        for i in range(20):
            if i < len(close_arr) - 1:
                hhv_i = np.max(high_arr[-i-21:-i-1]) if len(high_arr) > i+21 else np.max(high_arr[:len(high_arr)-i-1])
                llv_i = np.min(low_arr[-i-21:-i-1]) if len(low_arr) > i+21 else np.min(low_arr[:len(low_arr)-i-1])
                if llv_i != 0:
                    区间振幅_i = (hhv_i - llv_i) / llv_i * 100
                    if 区间振幅_i > 100:
                        exists_100 = True
                        break
        if exists_100:
            条件24得分 -= 0.4
        
        波幅 = np.mean(np.abs(high_arr[-30:] - low_arr[-30:]))
        prev_close = close_arr[-2] if len(close_arr) >= 2 else close
        波动率 = 波幅 / prev_close * 100 if prev_close != 0 else 0
        涨跌幅 = (close - prev_close) / prev_close * 100 if prev_close != 0 else 0
        大长阳 = close > open_p and 涨跌幅 > 波动率 * 1.5 and 涨跌幅 > 2
        大长阴 = close < open_p and abs(涨跌幅) > 波动率 * 1.1 and abs(涨跌幅) > 2
        参考成交量 = volume_arr[-2] if volume_arr[-1] <= volume / 8 else volume_arr[-1]
        关键K = close > close_arr[-2] and volume > 参考成交量 * 1.8 and 大长阳 and volume > np.mean(volume_arr[-40:]) if len(volume_arr) >= 40 else False
        暴力K = close > close_arr[-2] and volume > 参考成交量 * 1.8 and 涨跌幅 > 4 and (high - max(close, open_p)) <= (high - open_p) / 4 and volume > np.mean(volume_arr[-60:]) if len(volume_arr) >= 60 else False
        
        条件25得分 = 0
        跳空阳线_count = 0
        for i in range(20):
            if i < len(close_arr) - 1:
                low_i = low_arr[-i-1]
                high_prev = high_arr[-i-2]
                close_prev = close_arr[-i-2]
                gap_condition = (low_i - close_prev) / close_prev if close_prev != 0 else 0
                if close_arr[-i-1] >= open_arr[-i-1] and low_i > high_prev and (gap_condition > 0.032 or gap_condition > 波动率*0.01):
                    跳空阳线_count += 1
        if 跳空阳线_count >= 1:
            条件25得分 -= 1.2
            if 条件23得分 > 0:
                条件25得分 -= 1.0  # 通达信公式是-1分，不是+0.2分
        
        条件26得分 = 0
        if 条件23得分 == 0:
            # 通达信公式: 知行线波动平均 := (REF(知行多空线,15)+REF(知行多空线,30)+REF(知行多空线,45)+REF(知行多空线,60))/4
            # 即15/30/45/60天前的知行多空线的平均值
            if len(self.知行多空线_arr) >= 61:
                知行线波动平均 = (self.知行多空线_arr[-16] + self.知行多空线_arr[-31] + 
                               self.知行多空线_arr[-46] + self.知行多空线_arr[-61]) / 4
            else:
                知行线波动平均 = 知行多空线
            知行线平均_今 = (知行多空线 - 知行线波动平均) / 知行线波动平均 if 知行线波动平均 != 0 else 0
            # 通达信是分别计算后累加，不是累减
            if 知行线平均_今 < 0.05:
                条件26得分 -= 1.0
            elif 知行线平均_今 < 0.075:
                条件26得分 -= 0.8
            elif 知行线平均_今 < 0.10:
                条件26得分 -= 0.5
        
        条件27得分 = 0
        # 通达信: SUM(IF(C>O,V,0),20) > REF(SUM(IF(C>O,V,0),21),35)
        # REF(SUM...,21) 是21天前的20日阳量之和，即21-40天前
        sum_up_20 = np.sum(np.where(close_arr[-20:] > open_arr[-20:], volume_arr[-20:], 0))
        if len(close_arr) >= 41:
            sum_up_20_ref = np.sum(np.where(close_arr[-41:-21] > open_arr[-41:-21], volume_arr[-41:-21], 0))
            if sum_up_20 > sum_up_20_ref:
                条件27得分 = 0.5
            else:
                条件27得分 = -1
        
        条件28得分 = 0
        if 知行短期趋势线 < 知行短期趋势线_prev and 知行多空线 < 知行多空线_prev:
            条件28得分 = -2
        
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
        条件30得分 = 0
        if len(j_values) >= 2:  # 至少要有前一日的J值
            # 从前一日开始往前找15天内的最高J值
            j_prev_list = j_values[-16:-1]  # 前一日J值的最后15个值
            if len(j_prev_list) > 0:
                max_j_idx = np.argmax(j_prev_list)  # 找到最大值索引
                N = len(j_prev_list) - max_j_idx  # 距离最大值的周期数
                if 1 <= N <= 15:
                    YJ = j_values[-N-1]  # N天前的J值
                    YC = close_arr[-N-1]  # N天前的收盘价
                    if YJ > 95 and abs((close - YC) / YC * 100) <= 3:
                        high_n = np.max(high_arr[-N-1:]) if len(high_arr) > N+1 else np.max(high_arr)
                        low_n = np.min(low_arr[-N-1:]) if len(low_arr) > N+1 else np.min(low_arr)
                        if YC != 0 and (high_n - low_n) / YC * 100 < 12:
                            条件30得分 = 2.8
        
        条件31得分 = 0
        if len(volume_arr) >= 5:
            if (volume < volume_arr[-1] * 1.1 and volume_arr[-1] < volume_arr[-2] * 1.1 and 
                volume_arr[-2] < volume_arr[-3] * 1.1 and volume_arr[-3] < volume_arr[-4] * 1.1):
                if (close_arr[-1] < open_arr[-1] and close_arr[-2] < open_arr[-2] and 
                    close_arr[-3] < open_arr[-3] and close_arr[-4] < open_arr[-4]):
                    条件31得分 = -1
        
        波幅 = np.mean(np.abs(high_arr[-30:] - low_arr[-30:]))
        prev_close = close_arr[-2] if len(close_arr) >= 2 else close
        波动率 = 波幅 / prev_close * 100 if prev_close != 0 else 0
        涨跌幅 = (close - prev_close) / prev_close * 100 if prev_close != 0 else 0
        大长阳 = close > open_p and 涨跌幅 > 波动率 * 1.5 and 涨跌幅 > 2
        大长阴 = close < open_p and abs(涨跌幅) > 波动率 * 1.1 and abs(涨跌幅) > 2
        参考成交量 = volume_arr[-2] if volume_arr[-1] <= volume / 8 else volume_arr[-1]
        关键K = close > close_arr[-2] and volume > 参考成交量 * 1.8 and 大长阳 and volume > np.mean(volume_arr[-40:]) if len(volume_arr) >= 40 else False
        暴力K = close > close_arr[-2] and volume > 参考成交量 * 1.8 and 涨跌幅 > 4 and (high - max(close, open_p)) <= (high - open_p) / 4 and volume > np.mean(volume_arr[-60:]) if len(volume_arr) >= 60 else False
        
        条件32得分 = 0
        关键K_count = 0
        for i in range(20):
            if i < len(close_arr) - 1:
                涨跌幅_i = (close_arr[-i-1] - close_arr[-i-2]) / close_arr[-i-2] * 100 if close_arr[-i-2] != 0 else 0
                大长阳_i = close_arr[-i-1] > open_arr[-i-1] and 涨跌幅_i > 波动率 * 1.5 and 涨跌幅_i > 2
                if close_arr[-i-1] > close_arr[-i-2] and volume_arr[-i-1] > 参考成交量 * 1.8 and 大长阳_i and volume_arr[-i-1] > np.mean(volume_arr[-40:]):
                    关键K_count += 1
        if 关键K_count >= 1:
            条件32得分 = 1
        
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
        
        条件34得分 = 0
        # 计算60日最高成交量
        vol_hhv_60 = np.max(volume_arr[-60:]) if len(volume_arr) >= 60 else 0
        
        # 检查大长阴 + 成交量>前日*1.2 + 成交量>MA(VOL,60) + 成交量>(HHV(VOL,60))/1.95
        count_12 = 0
        for i in range(10):
            if i < len(close_arr) - 1:
                涨跌幅_i = (close_arr[-i-1] - close_arr[-i-2]) / close_arr[-i-2] * 100 if close_arr[-i-2] != 0 else 0
                大长阴_i = close_arr[-i-1] < open_arr[-i-1] and abs(涨跌幅_i) > 波动率 * 1.1 and abs(涨跌幅_i) > 2
                if 大长阴_i and volume_arr[-i-1] > volume_arr[-i-2] * 1.2 and volume_arr[-i-1] > np.mean(volume_arr[-60:]) and volume_arr[-i-1] > vol_hhv_60 / 1.95:
                    count_12 += 1
        if count_12 >= 1:
            条件34得分 -= 1
            
        # 检查大长阴 + 成交量>前日*1.4 + 成交量>MA(VOL,60) + 成交量>(HHV(VOL,60))/1.95
        count_14 = 0
        for i in range(10):
            if i < len(close_arr) - 1:
                涨跌幅_i = (close_arr[-i-1] - close_arr[-i-2]) / close_arr[-i-2] * 100 if close_arr[-i-2] != 0 else 0
                大长阴_i = close_arr[-i-1] < open_arr[-i-1] and abs(涨跌幅_i) > 波动率 * 1.1 and abs(涨跌幅_i) > 2
                if 大长阴_i and volume_arr[-i-1] > volume_arr[-i-2] * 1.4 and volume_arr[-i-1] > np.mean(volume_arr[-60:]) and volume_arr[-i-1] > vol_hhv_60 / 1.95:
                    count_14 += 1
        if count_14 >= 1:
            条件34得分 -= 0.6
            
        # 检查大长阴 + 成交量>前日*1.6 + 成交量>MA(VOL,60) + 成交量>(HHV(VOL,60))/1.95
        count_16 = 0
        for i in range(10):
            if i < len(close_arr) - 1:
                涨跌幅_i = (close_arr[-i-1] - close_arr[-i-2]) / close_arr[-i-2] * 100 if close_arr[-i-2] != 0 else 0
                大长阴_i = close_arr[-i-1] < open_arr[-i-1] and abs(涨跌幅_i) > 波动率 * 1.1 and abs(涨跌幅_i) > 2
                if 大长阴_i and volume_arr[-i-1] > volume_arr[-i-2] * 1.6 and volume_arr[-i-1] > np.mean(volume_arr[-60:]) and volume_arr[-i-1] > vol_hhv_60 / 1.95:
                    count_16 += 1
        if count_16 >= 1:
            条件34得分 -= 0.5
            
        # 检查大长阴 + 成交量>前日*1.8 + 成交量>MA(VOL,60) + 成交量>(HHV(VOL,60))/1.95
        count_18 = 0
        for i in range(10):
            if i < len(close_arr) - 1:
                涨跌幅_i = (close_arr[-i-1] - close_arr[-i-2]) / close_arr[-i-2] * 100 if close_arr[-i-2] != 0 else 0
                大长阴_i = close_arr[-i-1] < open_arr[-i-1] and abs(涨跌幅_i) > 波动率 * 1.1 and abs(涨跌幅_i) > 2
                if 大长阴_i and volume_arr[-i-1] > volume_arr[-i-2] * 1.8 and volume_arr[-i-1] > np.mean(volume_arr[-60:]) and volume_arr[-i-1] > vol_hhv_60 / 1.95:
                    count_18 += 1
        if count_18 >= 1:
            条件34得分 -= 0.4
            
        # 检查大长阴 + 成交量>前日*2.0 + 成交量>MA(VOL,60) + 成交量>(HHV(VOL,60))/1.95
        count_20 = 0
        for i in range(10):
            if i < len(close_arr) - 1:
                涨跌幅_i = (close_arr[-i-1] - close_arr[-i-2]) / close_arr[-i-2] * 100 if close_arr[-i-2] != 0 else 0
                大长阴_i = close_arr[-i-1] < open_arr[-i-1] and abs(涨跌幅_i) > 波动率 * 1.1 and abs(涨跌幅_i) > 2
                if 大长阴_i and volume_arr[-i-1] > volume_arr[-i-2] * 2.0 and volume_arr[-i-1] > np.mean(volume_arr[-60:]) and volume_arr[-i-1] > vol_hhv_60 / 1.95:
                    count_20 += 1
        if count_20 >= 1:
            条件34得分 -= 0.4
        
        条件35得分 = 1 if rsi2 > rsi3 and rsi3 > rsi4 else 0
        
        条件36得分 = 0
        涨停次数 = 0
        for i in range(20):
            if i < len(close_arr) - 1:
                # 检查是否是一字涨停 (O=C AND C=H AND C=涨停价)
                # 这里需要计算涨停价，但简化为检查是否是涨停状态
                if close_arr[-i-1] == open_arr[-i-1] and close_arr[-i-1] == high_arr[-i-1]:
                    # 检查是否接近涨停价（这里简化处理）
                    涨停次数 += 1
        if 涨停次数 >= 1:
            条件36得分 -= 1
        if 涨停次数 >= 2:
            条件36得分 -= 1.5
        
        条件37得分 = 0
        if open_p > 知行短期趋势线 and 知行短期趋势线 > 知行多空线 and close < 知行多空线 and close < open_p and volume > volume_arr[-1]:
            条件37得分 = -3
        
        条件38得分 = 0
        次高点_count = 0
        for i in range(10):
            if i < len(high_arr) - 1:
                # 检查次高点基础条件
                if len(high_arr) >= 60 and len(high_arr) >= i+5 and len(high_arr) >= i+61:
                    # 计算HHV(H, 4) - 从当前开始往前4个数据的最大值
                    start_idx = max(0, len(high_arr) - i - 4)
                    end_idx = len(high_arr) - i
                    hhv_h_4 = np.max(high_arr[start_idx:end_idx])
                    
                    # 计算HHV(H, 60) - 从当前开始往前60个数据的最大值
                    start_idx_60 = max(0, len(high_arr) - i - 60)
                    end_idx_60 = len(high_arr) - i
                    hhv_h_60 = np.max(high_arr[start_idx_60:end_idx_60])
                    
                    # 检查条件：HHV(H, 4) = HHV(H, 60) AND H <> HHV(H, 60)
                    condition1 = hhv_h_4 == hhv_h_60 and high_arr[-i-1] != hhv_h_60
                    
                    # 检查条件：(VOL > MA(VOL, 5) OR VOL > MA(VOL, 10))
                    vol_condition = False
                    if len(volume_arr) >= 5:
                        vol_condition = volume > np.mean(volume_arr[-5:]) or (len(volume_arr) >= 10 and volume > np.mean(volume_arr[-10:]))
                    
                    # 检查条件：C < O
                    price_condition = close_arr[-i-1] < open_arr[-i-1]
                    
                    # 检查条件：(((C / REF(C, 10) - 1) * 100 > 10) OR ((C / REF(C, 50) - 1) * 100 > 50))
                    growth_condition = False
                    if len(close_arr) >= i+12 and close_arr[-i-11] != 0:  # REF(C, 10)
                        growth_condition = (close_arr[-i-1] / close_arr[-i-11] - 1) * 100 > 10
                    if not growth_condition and len(close_arr) >= i+51 and close_arr[-i-51] != 0:  # REF(C, 50)
                        growth_condition = (close_arr[-i-1] / close_arr[-i-51] - 1) * 100 > 50
                    
                    # 检查次高点基础
                    if condition1 and vol_condition and price_condition and growth_condition:
                        # 检查前3天最高点位置
                        pos_start = max(0, len(high_arr) - i - 3)
                        pos_end = len(high_arr) - i
                        if pos_end > pos_start:
                            max_pos_in_3days = np.argmax(high_arr[pos_start:pos_end]) + pos_start
                            # REF(VOL, 前3天最高点位置) 是指max_pos_in_3days那天的成交量
                            ref_vol_idx = -(len(high_arr) - max_pos_in_3days)
                            if abs(ref_vol_idx) <= len(volume_arr):
                                ref_vol = volume_arr[ref_vol_idx]
                                if volume >= ref_vol * 0.8:
                                    次高点_count += 1
        if 次高点_count > 0:
            条件38得分 = -1
        
        条件39得分 = 0
        # 检查过去30天内 (C>O) AND (V>1.4*MA(V,90)) 的天数
        count_cond1 = 0
        for i in range(30):
            if i < len(close_arr) - 1 and len(volume_arr) >= 90:
                vol_ma90 = np.mean(volume_arr[-90:])
                if close_arr[-i-1] > open_arr[-i-1] and volume_arr[-i-1] > vol_ma90 * 1.4:
                    count_cond1 += 1
        
        # 检查过去30天内关键K的天数
        count_关键K = 0
        for i in range(30):
            if i < len(close_arr) - 1:
                涨跌幅_i = (close_arr[-i-1] - close_arr[-i-2]) / close_arr[-i-2] * 100 if close_arr[-i-2] != 0 else 0
                大长阳_i = close_arr[-i-1] > open_arr[-i-1] and 涨跌幅_i > 波动率 * 1.5 and 涨跌幅_i > 2
                if close_arr[-i-1] > close_arr[-i-2] and volume_arr[-i-1] > 参考成交量 * 1.8 and 大长阳_i and volume_arr[-i-1] > np.mean(volume_arr[-40:]) if len(volume_arr) >= 40 else False:
                    count_关键K += 1
        
        # 检查过去30天内暴力K的天数
        count_暴力K = 0
        for i in range(30):
            if i < len(close_arr) - 1:
                涨跌幅_i = (close_arr[-i-1] - close_arr[-i-2]) / close_arr[-i-2] * 100 if close_arr[-i-2] != 0 else 0
                if close_arr[-i-1] > close_arr[-i-2] and volume_arr[-i-1] > 参考成交量 * 1.8 and 涨跌幅_i > 4 and volume_arr[-i-1] > np.mean(volume_arr[-60:]) if len(volume_arr) >= 60 else False:
                    count_暴力K += 1
        
        if count_cond1 == 0 and count_关键K == 0 and count_暴力K == 0:
            条件39得分 = -2
        
        b1_score = (条件1得分 + 条件2得分 + 条件3得分 + 条件4得分 + 条件5得分 + 
                   条件6得分 + 条件7得分 + 条件8得分 + 条件9得分 + 条件10得分 +
                   条件11得分 + 条件12得分 + 条件13得分 + 条件14得分 + 条件15得分 +
                   条件16得分 + 条件17得分 + 条件18得分 + 条件19得分 + 条件20得分 +
                   条件21得分 + 条件22得分 + 条件23得分 + 条件24得分 + 条件25得分 +
                   条件26得分 + 条件27得分 + 条件28得分 + 条件29得分 + 条件30得分 +
                   条件31得分 + 条件32得分 + 条件33得分 + 条件34得分 + 条件35得分 +
                   条件36得分 + 条件37得分 + 条件38得分 + 条件39得分)
        
        if debug:
            print(f"\n=== B1各条件得分详情 ===")
            print(f"条件1得分(DIF>=0): {条件1得分}")
            print(f"条件2得分(C>MA60): {条件2得分}")
            print(f"条件3得分(涨幅-2~1.8): {条件3得分}")
            print(f"条件4得分(振幅<7): {条件4得分}")
            print(f"条件5得分(振幅<4): {条件5得分}")
            print(f"条件6得分(RSI<20/23): {条件6得分}")
            print(f"条件7得分(趋势线): {条件7得分}")
            print(f"条件8得分(地量30-10天): {条件8得分}")
            print(f"条件9得分(地量8-18天): {条件9得分}")
            print(f"条件10得分(地量20天): {条件10得分}")
            print(f"条件11得分(倍量+阳线): {条件11得分}")
            print(f"条件12得分(倍量+阴线): {条件12得分}")
            print(f"条件13得分(近期倍量+阴线): {条件13得分}")
            print(f"条件14得分(50/20日涨跌和): {条件14得分}")
            print(f"条件15得分(涨跌量对比): {条件15得分}")
            print(f"条件16得分(BBI>前20日BBI): {条件16得分}")
            print(f"条件17得分(支撑位距离): {条件17得分}")
            print(f"条件18得分(趋势线偏离): {条件18得分}")
            print(f"条件19得分(创业板趋势线): {条件19得分}")
            print(f"条件20得分(多空线偏离): {条件20得分}")
            print(f"条件21得分(价格区间): {条件21得分}")
            print(f"条件22得分(DIF背离): {条件22得分}")
            print(f"条件23得分(放量上涨): {条件23得分}")
            print(f"条件24得分(区间振幅): {条件24得分}")
            print(f"条件25得分(跳空阳线): {条件25得分}")
            print(f"条件26得分(知行线波动): {条件26得分}")
            print(f"条件27得分(成交量变化): {条件27得分}")
            print(f"条件28得分(趋势线下降): {条件28得分}")
            print(f"条件29得分(十字星): {条件29得分}")
            print(f"条件30得分(J值高位): {条件30得分}")
            print(f"条件31得分(缩量连续下跌): {条件31得分}")
            print(f"条件32得分(关键K): {条件32得分}")
            print(f"条件33得分(连续大长阳): {条件33得分}")
            print(f"条件34得分(大长阴): {条件34得分}")
            print(f"条件35得分(RSI多头): {条件35得分}")
            print(f"条件36得分(涨停次数): {条件36得分}")
            print(f"条件37得分(开盘压制): {条件37得分}")
            print(f"条件38得分(次高点): {条件38得分}")
            print(f"条件39得分(无关键K): {条件39得分}")
            print(f"\n>>> B1总分: {b1_score}")
        
        return b1_score
    
    def calculate_s1_score(self, close, high, low, open_price, close_arr, high_arr, low_arr, volume_arr, volume, dif, j, k, d, ma60, vol_ma60):
        前10日涨幅 = (close / close_arr[-10] - 1) * 100 > 10 if len(close_arr) >= 10 else False
        前50日涨幅 = (close / close_arr[-50] - 1) * 100 > 50 if len(close_arr) >= 50 else False
        
        条件1基础 = (close < open_price) and (high == np.max(high_arr[-60:])) and (前10日涨幅 or 前50日涨幅)
        
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
        
        # 修正前3天最高位距今的计算
        if len(high_arr) >= 3:
            # 找到最近3天内的最高点位置（从今天开始倒数）
            recent_3_high = high_arr[-3:]
            max_idx_in_recent_3 = np.argmax(recent_3_high)  # 返回0, 1, 或 2
            # 计算距离今天有多少天（0表示今天，1表示昨天，2表示前天）
            前3天最高位距今 = 2 - max_idx_in_recent_3  # 如果是最后一天就是0，倒数第二天是1，倒数第三天是2
        else:
            前3天最高位距今 = 0  # 如果数据不够，默认为0
        
        条件2基础 = False
        if len(high_arr) >= 60:
            hhv_h_4 = np.max(high_arr[-4:])
            hhv_h_60 = np.max(high_arr[-60:])
            if hhv_h_4 == hhv_h_60 and high != hhv_h_60:
                # 通达信MA包含今天，使用含今天的MA计算
                vol_ma5 = np.mean(volume_arr[-5:])
                vol_ma10 = np.mean(volume_arr[-10:])
                # 通达信涨幅: (C - REF(C,1)) / REF(C,1), REF(C,1) 是昨天收盘价
                涨幅 = (close - close_arr[-2]) / close_arr[-2] * 100 if close_arr[-2] != 0 else 0
                if (volume > vol_ma5 or volume > vol_ma10) and 涨幅 < -0.03 and close < open_price and (前10日涨幅 or 前50日涨幅):
                    条件2基础 = True
        
        条件2评分 = 0
        if 条件2基础 and 前3天最高位距今 >= 0 and 前3天最高位距今 < len(volume_arr):
            ref_vol = volume_arr[-前3天最高位距今-1] if 前3天最高位距今 < len(volume_arr) - 1 else volume_arr[-1]
            if volume >= ref_vol * 1.20:
                条件2评分 = 12
            elif volume >= ref_vol * 1.00:
                条件2评分 = 10
            elif volume >= ref_vol * 0.90:
                条件2评分 = 10
            elif volume >= ref_vol * 0.80:
                条件2评分 = 7.8
            elif volume >= ref_vol * 0.70:
                条件2评分 = 6.5
        
        条件2 = 条件2基础 and (volume >= volume_arr[-前3天最高位距今-1] * 0.70) if 前3天最高位距今 > 0 and 前3天最高位距今 < len(volume_arr) - 1 else False
        
        实体 = open_price - close
        上影线 = high - max(close, open_price)
        
        # 修复HHV(DIF, N)的计算
        # 计算每个历史点的DIF值，以便正确计算REF(HHV(DIF, N), offset)
        dif_history = []
        for i in range(len(close_arr)):
            # 计算每个点的DIF值
            hist_close = close_arr[-i-1] if i < len(close_arr) else close
            # 计算EMA12
            hist_ema12 = hist_close
            for j in range(1, min(12, i+1)):
                if i+j < len(close_arr):
                    hist_ema12 = hist_ema12 * (11/13) + close_arr[-i-1-j] * (2/13)
            
            # 计算EMA26
            hist_ema26 = hist_close
            for j in range(1, min(26, i+1)):
                if i+j < len(close_arr):
                    hist_ema26 = hist_ema26 * (25/27) + close_arr[-i-1-j] * (2/27)
            
            hist_dif = hist_ema12 - hist_ema26
            dif_history.append(hist_dif)
        
        # 计算HHV(DIF, 60), HHV(DIF, 40), HHV(DIF, 20)的历史值
        # 修正：假设通达信公式中的错误 0.7 实际上是想表示某种平均或偏移，我们采用合理的整数偏移
        # 通常REF(HHV(X, N), M) 表示N周期内X的最大值，M周期前的值
        # 如果0.7是错误，最可能是7或其他整数
        
        # 计算各种历史最大值
        hhv_dif_60 = np.max(dif_history[-60:]) if len(dif_history) >= 60 else dif
        hhv_dif_40 = np.max(dif_history[-40:]) if len(dif_history) >= 40 else dif
        hhv_dif_20 = np.max(dif_history[-20:]) if len(dif_history) >= 20 else dif
        
        # 修正：根据 TongDaXin 规范，REF(HHV(DIF, 60), 0.7) 中的 0.7 会被自动取整为 0
        # 实际等价于 REF(HHV(DIF, 60), 0)，也就是 HHV(DIF, 60) 本身
        ref_hhv_dif_60_offset = hhv_dif_60
        ref_hhv_dif_40_offset = hhv_dif_40
        ref_hhv_dif_20_offset = hhv_dif_20
        
        # 修复加分1：根据修正后的理解，REF(HHV(DIF, N), 0.7) 实际就是 HHV(DIF, N)
        加分1 = 0
        if 条件1:
            # 检查当前DIF是否小于历史最高DIF值
            if dif < ref_hhv_dif_60_offset:
                加分1 += 1
            if dif < ref_hhv_dif_40_offset:
                加分1 += 1
            if dif < ref_hhv_dif_20_offset:
                加分1 += 1
        
        加分2 = 0
        if 条件1 and 上影线 > 实体 / 2 and close > close_arr[-1]:
            加分2 += 0.5
        if 条件1 and 上影线 > 实体 and close > close_arr[-1]:
            加分2 += 0.5
        if 条件1 and 上影线 > 实体 * 2 and close > close_arr[-1]:
            加分2 += 0.5
        
        # 修复加分3：处理"该K线DIF < REF(HHV(DIF, 60),近3天最高位距今)"
        加分3 = 0
        if 条件2 and 前3天最高位距今 > 0 and len(dif_history) > 前3天最高位距今:
            # 获取前几天的DIF值作为"该K线DIF"
            该K线DIF = dif_history[前3天最高位距今] if 前3天最高位距今 < len(dif_history) else dif
            
            # 获取前"近3天最高位距今"周期前的HHV(DIF, 60)
            offset = 前3天最高位距今
            if len(dif_history) > 60 + offset:
                hist_hhv_dif_60_offset = np.max(dif_history[offset:offset+60]) if offset + 60 <= len(dif_history) else hhv_dif_60
            else:
                # 如果数据不够，使用当前的HHV值
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
    
    def calculate_s1_score_debug(self, close, high, low, open_price, close_arr, high_arr, low_arr, volume_arr, volume, dif, j, k, d, ma60, vol_ma60):
        前10日涨幅 = (close / close_arr[-10] - 1) * 100 > 10 if len(close_arr) >= 10 else False
        前50日涨幅 = (close / close_arr[-50] - 1) * 100 > 50 if len(close_arr) >= 50 else False
        
        条件1基础 = (close < open_price) and (high == np.max(high_arr[-60:])) and (前10日涨幅 or 前50日涨幅)
        
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
        
        # 修正前3天最高位距今的计算
        if len(high_arr) >= 3:
            # 找到最近3天内的最高点位置（从今天开始倒数）
            recent_3_high = high_arr[-3:]
            max_idx_in_recent_3 = np.argmax(recent_3_high)  # 返回0, 1, 或 2
            # 计算距离今天有多少天（0表示今天，1表示昨天，2表示前天）
            前3天最高位距今 = 2 - max_idx_in_recent_3  # 如果是最后一天就是0，倒数第二天是1，倒数第三天是2
        else:
            前3天最高位距今 = 0  # 如果数据不够，默认为0
        
        条件2基础 = False
        if len(high_arr) >= 60:
            hhv_h_4 = np.max(high_arr[-4:])
            hhv_h_60 = np.max(high_arr[-60:])
            if hhv_h_4 == hhv_h_60 and high != hhv_h_60:
                # 通达信MA包含今天，使用含今天的MA计算
                vol_ma5 = np.mean(volume_arr[-5:])
                vol_ma10 = np.mean(volume_arr[-10:])
                # 通达信涨幅: (C - REF(C,1)) / REF(C,1), REF(C,1) 是昨天收盘价
                涨幅 = (close - close_arr[-2]) / close_arr[-2] * 100 if close_arr[-2] != 0 else 0
                if (volume > vol_ma5 or volume > vol_ma10) and 涨幅 < -0.03 and close < open_price and (前10日涨幅 or 前50日涨幅):
                    条件2基础 = True
        
        条件2评分 = 0
        if 条件2基础 and 前3天最高位距今 >= 0 and 前3天最高位距今 < len(volume_arr):
            ref_vol = volume_arr[-前3天最高位距今-1] if 前3天最高位距今 < len(volume_arr) - 1 else volume_arr[-1]
            if volume >= ref_vol * 1.20:
                条件2评分 = 12
            elif volume >= ref_vol * 1.00:
                条件2评分 = 10
            elif volume >= ref_vol * 0.90:
                条件2评分 = 10
            elif volume >= ref_vol * 0.80:
                条件2评分 = 7.8
            elif volume >= ref_vol * 0.70:
                条件2评分 = 6.5
        
        条件2 = 条件2基础 and (volume >= volume_arr[-前3天最高位距今-1] * 0.70) if 前3天最高位距今 > 0 and 前3天最高位距今 < len(volume_arr) - 1 else False
        
        实体 = open_price - close
        上影线 = high - max(close, open_price)
        
        # 修复HHV(DIF, N)的计算
        # 计算每个历史点的DIF值，以便正确计算REF(HHV(DIF, N), offset)
        dif_history = []
        for i in range(len(close_arr)):
            # 计算每个点的DIF值
            hist_close = close_arr[-i-1] if i < len(close_arr) else close
            # 计算EMA12
            hist_ema12 = hist_close
            for j in range(1, min(12, i+1)):
                if i+j < len(close_arr):
                    hist_ema12 = hist_ema12 * (11/13) + close_arr[-i-1-j] * (2/13)
            
            # 计算EMA26
            hist_ema26 = hist_close
            for j in range(1, min(26, i+1)):
                if i+j < len(close_arr):
                    hist_ema26 = hist_ema26 * (25/27) + close_arr[-i-1-j] * (2/27)
            
            hist_dif = hist_ema12 - hist_ema26
            dif_history.append(hist_dif)
        
        # 计算HHV(DIF, 60), HHV(DIF, 40), HHV(DIF, 20)的历史值
        # 修正：假设通达信公式中的错误 0.7 实际上是想表示某种平均或偏移，我们采用合理的整数偏移
        # 通常REF(HHV(X, N), M) 表示N周期内X的最大值，M周期前的值
        # 如果0.7是错误，最可能是7或其他整数
        
        # 计算各种历史最大值
        hhv_dif_60 = np.max(dif_history[-60:]) if len(dif_history) >= 60 else dif
        hhv_dif_40 = np.max(dif_history[-40:]) if len(dif_history) >= 40 else dif
        hhv_dif_20 = np.max(dif_history[-20:]) if len(dif_history) >= 20 else dif
        
        # 修正：根据 TongDaXin 规范，REF(HHV(DIF, 60), 0.7) 中的 0.7 会被自动取整为 0
        # 实际等价于 REF(HHV(DIF, 60), 0)，也就是 HHV(DIF, 60) 本身
        ref_hhv_dif_60_offset = hhv_dif_60
        ref_hhv_dif_40_offset = hhv_dif_40
        ref_hhv_dif_20_offset = hhv_dif_20
        
        # 修复加分1：根据修正后的理解，REF(HHV(DIF, N), 0.7) 实际就是 HHV(DIF, N)
        加分1 = 0
        if 条件1:
            # 检查当前DIF是否小于历史最高DIF值
            if dif < ref_hhv_dif_60_offset:
                加分1 += 1
            if dif < ref_hhv_dif_40_offset:
                加分1 += 1
            if dif < ref_hhv_dif_20_offset:
                加分1 += 1
        
        加分2 = 0
        if 条件1 and 上影线 > 实体 / 2 and close > close_arr[-1]:
            加分2 += 0.5
        if 条件1 and 上影线 > 实体 and close > close_arr[-1]:
            加分2 += 0.5
        if 条件1 and 上影线 > 实体 * 2 and close > close_arr[-1]:
            加分2 += 0.5
        
        # 修复加分3：处理"该K线DIF < REF(HHV(DIF, 60),近3天最高位距今)"
        加分3 = 0
        if 条件2 and 前3天最高位距今 > 0 and len(dif_history) > 前3天最高位距今:
            # 获取前几天的DIF值作为"该K线DIF"
            该K线DIF = dif_history[前3天最高位距今] if 前3天最高位距今 < len(dif_history) else dif
            
            # 获取前"近3天最高位距今"周期前的HHV(DIF, 60)
            offset = 前3天最高位距今
            if len(dif_history) > 60 + offset:
                hist_hhv_dif_60_offset = np.max(dif_history[offset:offset+60]) if offset + 60 <= len(dif_history) else hhv_dif_60
            else:
                # 如果数据不够，使用当前的HHV值
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
        
        print("=== S1各条件得分详情 ===")
        print(f"条件1基础: {条件1基础}, 条件1: {条件1}, 条件1评分: {条件1评分}")
        print(f"条件2基础: {条件2基础}, 条件2: {条件2}, 条件2评分: {条件2评分}")
        print(f"前3天最高位距今: {前3天最高位距今}")
        print(f"Hhv_DIF_60: {hhv_dif_60:.4f}, Hhv_DIF_40: {hhv_dif_40:.4f}, Hhv_DIF_20: {hhv_dif_20:.4f}")
        print(f"加分1 (DIF < HHV): {加分1}")
        print(f"加分2 (上影线实体关系): {加分2}")
        print(f"加分3 (该K线DIF < HHV): {加分3}")
        print(f"加分4 (J<K<D): {加分4}")
        print(f"加分5 (条件1或2且收跌): {加分5}")
        print(f"加分6 (天量柱): {加分6}")
        
        s1_score = 条件1评分 + 条件2评分 + 加分1 + 加分2 + 加分3 + 加分4 + 加分5 + 加分6
        return s1_score
    
    def next(self):
        if len(self) <= 5:
            return
        
        if len(self) < 60:
            return
        
        if self.order:
            return
        
        close = self.close[0]
        open_price = self.open[0]
        high = self.high[0]
        low = self.low[0]
        volume = self.volume[0]
        
        current_date = self.datas[0].datetime.datetime(0)
        
        close_arr = np.array(self.close.array[:len(self)])
        high_arr = np.array(self.high.array[:len(self)])
        low_arr = np.array(self.low.array[:len(self)])
        volume_arr = np.array(self.volume.array[:len(self)])
        open_arr = np.array(self.open.array[:len(self)])
        
        ma5 = np.mean(close_arr[-5:])
        ma10 = np.mean(close_arr[-10:])
        ma20 = np.mean(close_arr[-20:])
        ma60 = np.mean(close_arr[-60:])
        
        ma14 = np.mean(close_arr[-14:])
        ma28 = np.mean(close_arr[-28:])
        ma57 = np.mean(close_arr[-57:])
        ma114 = np.mean(close_arr[-114:])
        
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
        
        ema12 = close_arr[-1]
        for i in range(2, 13):
            if i < len(close_arr):
                ema12 = ema12 * (2/13) + close_arr[-i] * (1 - 2/13)
        
        ema26 = close_arr[-1]
        for i in range(2, 27):
            if i < len(close_arr):
                ema26 = ema26 * (2/27) + close_arr[-i] * (1 - 2/27)
        
        dif = ema12 - ema26
        
        ema10_1 = close_arr[-1]
        for i in range(2, 11):
            if i < len(close_arr):
                ema10_1 = ema10_1 * (2/11) + close_arr[-i] * (1 - 2/11)
        
        ema10_2 = ema10_1
        for i in range(2, 11):
            if i < len(close_arr):
                ema10_2 = ema10_2 * (2/11) + ema10_1 * (1 - 2/11)
        
        知行短期趋势线 = ema10_2
        知行多空线 = (ma14 + ma28 + ma57 + ma114) / 4
        
        self.知行短期趋势线_arr.append(知行短期趋势线)
        self.知行多空线_arr.append(知行多空线)
        
        prev_close = self.close[-1]
        
        涨幅 = (close - prev_close) / prev_close * 100 if prev_close != 0 else 0
        振幅 = (high - low) / prev_close * 100 if prev_close != 0 else 0
        
        vol_ma60 = np.mean(volume_arr[-60:])
        
        ma3 = np.mean(close_arr[-3:])
        ma6 = np.mean(close_arr[-6:])
        ma12 = np.mean(close_arr[-12:])
        ma24 = np.mean(close_arr[-24:])
        bbi = (ma3 + ma6 + ma12 + ma24) / 4
        
        # 通达信公式: 前20日BBI:=REF(BBI,20) - 20天前的BBI值
        if len(self) >= 21:
            ma3_20 = np.mean(close_arr[-23:-20]) if len(close_arr) >= 23 else close_arr[-1]
            ma6_20 = np.mean(close_arr[-26:-20]) if len(close_arr) >= 26 else close_arr[-1]
            ma12_20 = np.mean(close_arr[-32:-20]) if len(close_arr) >= 32 else close_arr[-1]
            ma24_20 = np.mean(close_arr[-44:-20]) if len(close_arr) >= 44 else close_arr[-1]
            前20日BBI = (ma3_20 + ma6_20 + ma12_20 + ma24_20) / 4
        else:
            前20日BBI = bbi
        
        gains = []
        losses = []
        for i in range(1, 15):
            if i < len(close_arr):
                diff = close_arr[-i] - close_arr[-i-1]
                gains.append(max(diff, 0))
                losses.append(max(-diff, 0))
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0.001
        rs = avg_gain / avg_loss
        rsi1 = 100 - (100 / (1 + rs))
        
        gains2, losses2 = [], []
        for i in range(14):
            if i < len(close_arr) - 1:
                change = close_arr[-i-1] - close_arr[-i-2]
                if change > 0:
                    gains2.append(change)
                else:
                    losses2.append(abs(change))
        avg_gain2 = np.mean(gains2) if gains2 else 0
        avg_loss2 = np.mean(losses2) if losses2 else 0.001
        rs2 = avg_gain2 / avg_loss2 if avg_loss2 != 0 else avg_gain2 / 0.001
        rsi2 = 100 - (100 / (1 + rs2))
        
        gains3, losses3 = [], []
        for i in range(28):
            if i < len(close_arr) - 1:
                change = close_arr[-i-1] - close_arr[-i-2]
                if change > 0:
                    gains3.append(change)
                else:
                    losses3.append(abs(change))
        avg_gain3 = np.mean(gains3) if gains3 else 0
        avg_loss3 = np.mean(losses3) if losses3 else 0.001
        rs3 = avg_gain3 / avg_loss3 if avg_loss3 != 0 else avg_gain3 / 0.001
        rsi3 = 100 - (100 / (1 + rs3))
        
        gains4, losses4 = [], []
        for i in range(57):
            if i < len(close_arr) - 1:
                change = close_arr[-i-1] - close_arr[-i-2]
                if change > 0:
                    gains4.append(change)
                else:
                    losses4.append(abs(change))
        avg_gain4 = np.mean(gains4) if gains4 else 0
        avg_loss4 = np.mean(losses4) if losses4 else 0.001
        rs4 = avg_gain4 / avg_loss4 if avg_loss4 != 0 else avg_gain4 / 0.001
        rsi4 = 100 - (100 / (1 + rs4))
        
        prev_close = self.close[-2] if len(self) >= 2 else close_arr[-2]
        prev_涨幅 = (close - prev_close) / prev_close * 100 if prev_close != 0 else 0
        波幅 = np.mean(np.abs(high_arr[-30:] - low_arr[-30:]))
        波动率 = 波幅 / prev_close * 100 if prev_close != 0 else 0
        涨跌幅 = 涨幅
        K线长度 = high - open_price
        上影线 = high - max(close, open_price)
        
        if len(self) >= 2 and len(self.知行短期趋势线_arr) >= 2:
            知行短期趋势线_prev = self.知行短期趋势线_arr[-2]
            知行多空线_prev = self.知行多空线_arr[-2]
        else:
            知行短期趋势线_prev = 知行短期趋势线
            知行多空线_prev = 知行多空线
        
        low_9 = np.min(low_arr[-9:])
        high_9 = np.max(high_arr[-9:])
        rsv_k = (close - low_9) / (high_9 - low_9) * 100 if high_9 != low_9 else 50
        
        if self.prev_k is None:
            k = rsv_k
        else:
            k = (2.0 / 3.0) * self.prev_k + (1.0 / 3.0) * rsv_k
        
        if self.prev_d is None:
            d = k
        else:
            d = (2.0 / 3.0) * self.prev_d + (1.0 / 3.0) * k
        
        self.prev_k = k
        self.prev_d = d
        
        j = 3 * k - 2 * d
        
        global j_values
        j_values = []
        for i in range(1, 4):
            if i < len(close_arr):
                low_9_i = np.min(low_arr[-9-i:-i]) if i < len(low_arr) else np.min(low_arr[-9:])
                high_9_i = np.max(high_arr[-9-i:-i]) if i < len(high_arr) else np.max(high_arr[-9:])
                close_i = close_arr[-i-1] if i < len(close_arr) else close_arr[-1]
                rsv_k_i = (close_i - low_9_i) / (high_9_i - low_9_i) * 100 if high_9_i != low_9_i else 50
                j_i = 3 * rsv_k_i - 2 * rsv_k_i
                j_values.append(j_i)
        
        KDJ_J低 = j < 13
        MACD_多头 = dif >= 0
        趋势线条件 = 知行短期趋势线 > 知行多空线
        
        b1_score = self.calculate_b1_score(close, high, open_price, open_arr, close_arr, high_arr, low_arr, volume_arr, volume, dif, dif_arr, rsi1, rsi2, rsi3, rsi4, j, 知行短期趋势线, 知行多空线, 知行短期趋势线_prev, 知行多空线_prev, bbi, 前20日BBI, 涨幅, 振幅, debug=False)
        
        # 保存当前B1分数和相关值
        self.current_b1_score = b1_score
        self.current_j_value = j
        self.current_dif_value = dif
        
        B1总分 = b1_score if b1_score > 0 else 0
        
        buy_condition = (not self.st_days and KDJ_J低 and MACD_多头 and 趋势线条件 and B1总分 >= self.p.b1_threshold)

        buy_condition_pre = (not self.st_days and KDJ_J低 and MACD_多头 and 趋势线条件 and B1总分 >= 3.5)
        if buy_condition_pre:
            print(f"\n=== B1分数详情 ===")
            print(f"日期: {current_date.strftime('%Y-%m-%d')}")
            print(f"收盘价: {close}, 开盘价: {open_price}, 最高价: {high}")
            print(f"DIF: {dif:.4f}, RSI1: {rsi1:.2f}")
            print(f"知行短期趋势线: {知行短期趋势线:.4f}, 知行多空线: {知行多空线:.4f}")
            print(f"BBI: {bbi:.4f}, 前20日BBI: {前20日BBI:.4f}")
            print(f"涨幅: {涨幅:.2f}%, 振幅: {振幅:.2f}%")
            print(f"K: {k:.2f}, D: {d:.2f}, J值: {j:.2f}, KDJ_J低: {j < 13}")
            print(f"B1总分: {B1总分}")
        
        if not self.position:
            # 检查时间过滤
            is_filtered, filter_reason = self.is_time_filtered()
            
            if self.pending_buy_signal:
                # 尝试执行挂单买入
                if is_filtered:
                    print(f"[买入延迟] {current_date.strftime('%Y-%m-%d')}: {filter_reason}，挂单取消")
                    self.pending_buy_signal = False
                    self.pending_buy_reason = ""
                    return
                
                print(f"[挂单] {current_date.strftime('%Y-%m-%d')}: 原因={self.pending_buy_reason}")
                cash = self.broker.getcash()
                # 预留10%资金作为手续费和滑点缓冲
                available_cash = cash * 0.9
                size = int(available_cash / close / 100) * 100
                print(f"[挂单检查] 现金={cash:.2f}, 可用={available_cash:.2f}, 价格={close}, 可买数量={size}")
                if size >= 100:
                    self.order = self.buy(size=size)
                    self.entry_price = close
                else:
                    print(f"资金不足无法买入: 现金={cash:.2f}, 价格={close}, 最小需={close*100:.2f}")
                self.pending_buy_signal = False
                self.pending_buy_reason = ""
                return
            
            if buy_condition:
                if is_filtered:
                    # 被过滤时设置pending信号，但不打印，等待下一个bar
                    self.pending_buy_signal = True
                    self.pending_buy_reason = f"B1总分={B1总分:.1f}, J={j:.1f}, DIF={dif:.2f}"
                    print(f"检测到买入信号: 日期={current_date.strftime('%Y-%m-%d')}, B1总分={B1总分:.1f}, J={j:.1f}, 但{filter_reason}，延迟买入")
                else:
                    self.pending_buy_signal = True
                    self.pending_buy_reason = f"B1总分={B1总分:.1f}, J={j:.1f}, DIF={dif:.2f}"
                    self.pending_b1_score = B1总分  # 保存信号产生时的B1分数
        else:
            current_price = close
            profit_pct = (current_price - self.entry_price) / self.entry_price
            
            s1_score = self.calculate_s1_score(close, high, low, open_price, close_arr, high_arr, low_arr, volume_arr, volume, dif, j, k, d, ma60, vol_ma60)
            
            # Add detailed logging for specific dates mentioned by user
            if current_date.strftime('%Y-%m-%d') in ['2025-08-27', '2025-09-08']:
                print(f"\n=== {current_date.strftime('%Y-%m-%d')} S1分数详情 ===")
                print(f"收盘价: {close}, 开盘价: {open_price}, 最高价: {high}, 最低价: {low}")
                print(f"DIF: {dif:.4f}, J: {j:.2f}, K: {k:.2f}, D: {d:.2f}")
                print(f"成交量: {volume}, MA60: {ma60:.2f}, VOL_MA60: {vol_ma60:.2f}")
                print(f"前10日涨幅: {(close / close_arr[-10] - 1) * 100 if len(close_arr) >= 10 else 0:.2f}%")
                print(f"前50日涨幅: {(close / close_arr[-50] - 1) * 100 if len(close_arr) >= 50 else 0:.2f}%")
                
                # Calculate S1 score with debug info
                s1_score_debug = self.calculate_s1_score_debug(close, high, low, open_price, close_arr, high_arr, low_arr, volume_arr, volume, dif, j, k, d, ma60, vol_ma60)
                print(f"S1总分: {s1_score_debug}")
            
            if self.pending_sell_reason:
                # 记录卖出操作日期（订单提交日），用于后续记录
                sell_op_date = current_date.strftime('%Y-%m-%d')
                self.pending_sell_date = sell_op_date
                
                if self.pending_sell_half:
                    print(f"卖出日期: {current_date.strftime('%Y-%m-%d')}, 原因: {self.pending_sell_reason}, S1={s1_score:.1f}, 收益率: {profit_pct*100:.2f}%")
                    self.order = self.sell(size=self.position.size // 2)
                    self.s1_half_sold = True
                    self.pending_sell_half = False
                else:
                    print(f"卖出日期: {current_date.strftime('%Y-%m-%d')}, 原因: {self.pending_sell_reason}, S1={s1_score:.1f}, 收益率: {profit_pct*100:.2f}%")
                    self.order = self.sell(size=self.position.size)
                self.pending_sell_reason = ""
                return
            
            if s1_score > 10:
                self.pending_sell_reason = f"S1清仓(S1={s1_score:.1f}>10)"
                self.pending_sell_date = current_date.strftime('%Y-%m-%d')
                self.pending_sell_half = False
                return
            
            if s1_score > 5 and not self.s1_half_sold:
                self.pending_sell_reason = f"S1半仓(S1={s1_score:.1f}>5)"
                self.pending_sell_date = current_date.strftime('%Y-%m-%d')
                self.pending_sell_half = True
                return
            
            # 禁用止损条件，只用S1分数和跌破多空线卖出
            # if profit_pct <= -self.p.stop_loss_pct:
            #     sell_reason = f"止损(-{abs(profit_pct)*100:.2f}%)"
            #     self.pending_sell_date = current_date.strftime('%Y-%m-%d')
            #     self.order = self.sell(size=self.position.size)
            #     print(f"卖出日期: {current_date.strftime('%Y-%m-%d')}, 原因: {sell_reason}")
                return
            
            if close < 知行多空线:
                # 多空线跌破缓冲机制
                if self.p.多空线缓冲 and not self.多空线跌破观察:
                    # 首次跌破，设置观察期
                    self.多空线跌破观察 = True
                    self.pending_sell_reason = f"跌破知行多空线观察({close:.2f}<{知行多空线:.2f})"
                    self.pending_sell_date = current_date.strftime('%Y-%m-%d')
                    return
                elif self.多空线跌破观察 and close < 知行多空线:
                    # 连续跌破，执行卖出
                    self.pending_sell_reason = f"跌破知行多空线确认({close:.2f}<{知行多空线:.2f})"
                    self.pending_sell_date = current_date.strftime('%Y-%m-%d')
                    self.多空线跌破观察 = False  # 重置
                    return
                else:
                    # 回到多空线之上，取消观察和待卖出
                    self.多空线跌破观察 = False
                    if self.pending_sell_reason and "跌破知行多空线" in self.pending_sell_reason:
                        self.pending_sell_reason = ""
                        print(f"卖出取消: 价格回到知行多空线之上")
    
    def notify_order(self, order):
        # 打印订单状态变化
        status_name = {
            order.Submitted: 'Submitted',
            order.Partial: 'Partial', 
            order.Completed: 'Completed',
            order.Canceled: 'Canceled',
            order.Rejected: 'Rejected',
            order.Margin: 'Margin',
        }.get(order.status, f'Unknown({order.status})')
        
        print(f"[订单状态] {status_name}: {'买入' if order.isbuy() else '卖出'}, 价格={order.executed.price if order.executed.price else order.price}, 数量={order.executed.size if order.executed.size else order.size}")
        
        if order.status in [order.Completed]:
            date = self.datas[0].datetime.date(0)
            if order.isbuy():
                print(f"[成交] 买入: {date}, 价格: {order.executed.price:.2f}, 数量: {order.executed.size}")
                
                # 记录买入交易
                trade_record = {
                    'date': date,
                    'action': 'BUY',
                    'price': order.executed.price,
                    'size': order.executed.size,
                    'b1_score': self.pending_b1_score,  # 使用信号产生时的B1分数
                    'j_value': self.current_j_value,
                    'dif_value': self.current_dif_value,
                    'reason': getattr(self, 'pending_buy_reason', ''),
                    'position': order.executed.size,  # 买入仓位
                    'pnl': 0  # 初始盈亏为0
                }
                self.trade_records.append(trade_record)
                
            elif order.issell():
                print(f"[成交] 卖出: {date}, 价格: {order.executed.price:.2f}, 数量: {order.executed.size}")
                
                # 使用卖出信号日期而非成交日期
                record_date = self.pending_sell_date if self.pending_sell_date else date
                
                # 计算单次收益
                pnl = 0
                if hasattr(self, 'entry_price') and self.entry_price:
                    # 单次收益 = (卖出价格 - 买入价格) / 买入价格 * 100%
                    pnl = (order.executed.price - self.entry_price) / self.entry_price * 100
                
                # 记录卖出交易
                record_date = self.pending_sell_date if self.pending_sell_date else date
                trade_record = {
                    'date': record_date,
                    'action': 'SELL',
                    'price': order.executed.price,
                    'size': order.executed.size,
                    'b1_score': self.current_b1_score,
                    'j_value': self.current_j_value,
                    'dif_value': self.current_dif_value,
                    'reason': getattr(self, 'pending_sell_reason', ''),
                    'position': order.executed.size,  # 卖出仓位（负值表示卖空）
                    'pnl': pnl  # 单次收益百分比
                }
                self.trade_records.append(trade_record)
                
            self.order = None


def run_backtest(stock_code="300486", start_date="20240101", end_date="20241231", initial_cash=100000):
    print(f"=== 天宫B1策略回测 ===")
    print(f"股票代码：{stock_code}")
    print(f"回测期间：{start_date} 至 {end_date}")
    print(f"初始资金：{initial_cash:.2f} 元")
    print(f"买入条件: 非ST股 AND KDJ_J低(J<13) AND MACD_多头(DIF>=0) AND 知行短期趋势线>知行多空线 AND B1总分>=8")
    print(f"卖出条件: S1>10清仓/S1>5半仓/跌破知行多空线/止损5%")
    
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.001, stocklike=True, commtype=bt.CommInfoBase.COMM_PERC)
    cerebro.broker.set_slippage_perc(0.001)
    
    try:
        # 从Astock3数据库获取数据
        db = duckdb.connect('data/Astock3.duckdb')
        
        # 转换日期格式
        start_date_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end_date_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
        
        df = db.execute(f"""
            SELECT trade_date as date, open, high, low, close, vol as volume, amount
            FROM dwd_daily_price 
            WHERE ts_code = '{stock_code}' 
            AND trade_date >= '{start_date_fmt}' 
            AND trade_date <= '{end_date_fmt}'
            ORDER BY trade_date
        """).fetchdf()
        
        db.close()
        
        if df is None or len(df) == 0:
            print(f"未在数据库中找到 {stock_code} 的数据")
            return
        
        print(f"\n从数据库获取到 {len(df)} 条数据")
        
        df.rename(columns={
            'date': 'datetime',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'openinterest'
        }, inplace=True)
        
        print(f"数据起始日期：{df['datetime'].iloc[0]}")
        print(f"数据结束日期：{df['datetime'].iloc[-1]}")
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        data = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data)
    except Exception as e:
        import traceback
        print(f"数据获取失败：{e}")
        traceback.print_exc()
        return
    
    cerebro.addstrategy(TiangongB1Strategy)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analysis')
    
    results = cerebro.run()
    final_cash = cerebro.broker.getvalue()
    
    print(f"\n{'='*50}")
    print(f"=== 回测结果 ===")
    print(f"最终资金：{final_cash:.2f} 元")
    total_return = (final_cash - initial_cash)/initial_cash * 100
    print(f"总收益率：{total_return:.2f}%")
    
    strat = results[0]
    
    sharpe = strat.analyzers.sharpe.get_analysis()
    sharpe_ratio = sharpe.get('sharperatio', 0) if sharpe else 0
    if sharpe_ratio is None:
        sharpe_ratio = 0
    if sharpe and sharpe.get('sharperatio'):
        print(f"夏普比率：{sharpe['sharperatio']:.4f}")
    else:
        print(f"夏普比率：0.0000")
    
    drawdown = strat.analyzers.drawdown.get_analysis()
    max_drawdown = drawdown['max'].get('drawdown', 0) if drawdown and drawdown.get('max') else 0
    print(f"最大回撤：{max_drawdown:.2f}%")
    
    returns = strat.analyzers.returns.get_analysis()
    annual_return = returns.get('rnorm100', 0) if returns else 0
    print(f"年化收益率：{annual_return:.2f}%")
    
    trade_analysis = strat.analyzers.trade_analysis.get_analysis()
    if trade_analysis:
        total_trades = trade_analysis.get('total', {}).get('total', 0)
        won_trades = trade_analysis.get('won', {}).get('total', 0)
        lost_trades = trade_analysis.get('lost', {}).get('total', 0)
        win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0
        
        print(f"\n=== 交易统计 ===")
        print(f"总交易次数：{total_trades}")
        print(f"盈利交易：{won_trades}")
        print(f"亏损交易：{lost_trades}")
        print(f"胜率：{win_rate:.2f}%")
    
    # 导出CSV报告
    export_to_csv("天宫B1策略", total_return, annual_return, win_rate, total_trades, max_drawdown, 
                  sharpe_ratio, strat.trade_records, stock_code, start_date, end_date)
    
    print(f"\n{'='*50}")
    print(f"=== 回测完成 ===")


def export_to_csv(strategy_name, total_return, annual_return, win_rate, total_trades, max_drawdown, 
                  sharpe_ratio, trade_records, stock_code, start_date, end_date):
    """导出回测结果到CSV文件"""
    csv_dir = "回测csv"
    csv_file = os.path.join(csv_dir, "天宫B1策略回测.csv")
    
    # 如果目录不存在，创建目录
    if not os.path.exists(csv_dir):
        os.makedirs(csv_dir)
    
    # 获取交易记录中的买入和卖出配对
    buys = []
    sells = []
    for record in trade_records:
        if record['action'] == 'BUY':
            buys.append(record)
        elif record['action'] == 'SELL':
            sells.append(record)
    
    # 如果文件不存在，创建带表头的文件
    if not os.path.exists(csv_file):
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                '策略名称', '总收益率', '年化收益率', '胜率', '交易次数', '最大回撤', '夏普比率', 
                'alpha', 'beta', '买入时间', '卖出时间', '买入信号得分', '卖出信号得分', 
                '买入仓位', '卖出仓位', '单次收益%', '备注'
            ])
    
    # 将交易记录写入CSV
    with open(csv_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # 如果有交易记录，则逐条写入
        if buys or sells:
            # 按交易顺序匹配买卖记录
            max_len = max(len(buys), len(sells))
            for i in range(max_len):
                buy_record = buys[i] if i < len(buys) else {}
                sell_record = sells[i] if i < len(sells) else {}
                
                # 获取买入和卖出信息
                buy_date = buy_record.get('date', '') if buy_record else ''
                sell_date = sell_record.get('date', '') if sell_record else ''
                buy_b1_score = buy_record.get('b1_score', '') if buy_record else ''
                sell_b1_score = sell_record.get('b1_score', '') if sell_record else ''
                buy_reason = buy_record.get('reason', '') if buy_record else ''
                sell_reason = sell_record.get('reason', '') if sell_record else ''
                buy_position = buy_record.get('position', '') if buy_record else ''
                sell_position = sell_record.get('position', '') if sell_record else ''
                pnl = sell_record.get('pnl', '') if sell_record else ''  # 单次收益来自卖出记录
                
                writer.writerow([
                    strategy_name, 
                    round(total_return, 2), 
                    round(annual_return, 2), 
                    round(win_rate, 2), 
                    total_trades, 
                    round(max_drawdown, 2), 
                    round(sharpe_ratio, 4), 
                    '',  # alpha
                    '',  # beta
                    buy_date, 
                    sell_date, 
                    round(buy_b1_score, 2) if buy_b1_score != '' and buy_b1_score is not None else '', 
                    round(sell_b1_score, 2) if sell_b1_score != '' and sell_b1_score is not None else '', 
                    buy_position,
                    sell_position,
                    round(pnl, 2) if pnl != '' and pnl is not None else '',
                    f"股票:{stock_code}, 期间:{start_date}-{end_date}, {buy_reason};{sell_reason}"
                ])
        else:
            # 如果没有交易记录，写入总体结果
            writer.writerow([
                strategy_name, 
                round(total_return, 2), 
                round(annual_return, 2), 
                round(win_rate, 2), 
                total_trades, 
                round(max_drawdown, 2), 
                round(sharpe_ratio, 4), 
                '',  # alpha
                '',  # beta
                '',  # 买入时间
                '',  # 卖出时间
                '',  # 买入信号得分
                '',  # 卖出信号得分
                '',  # 买入仓位
                '',  # 卖出仓位
                '',  # 单次收益%
                f"股票:{stock_code}, 期间:{start_date}-{end_date}, 无交易"
            ])


if __name__ == "__main__":
    run_backtest(
        stock_code="300486",
        start_date="20250101",
        end_date="20251231",
        initial_cash=100000
    )

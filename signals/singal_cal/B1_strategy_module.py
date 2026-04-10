import os
import logging
from datetime import datetime
import numpy as np
from basic_module import calculate_知行多空线_arr
from basic_module import calculate_知行短期趋势线_arr


# 配置路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 配置日志
LOG_FILE = os.path.join(LOG_DIR, f'scan_signals_{datetime.now().strftime("%Y%m%d")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def calculate_b1_score(indicators):
    code = indicators['code']
    open = indicators['open']
    close = indicators['close']
    high = indicators['high']
    low = indicators['low']
    volume = indicators['volume']

    open_arr = indicators['open_arr']
    close_arr = indicators['close_arr']
    high_arr = indicators['high_arr']
    low_arr = indicators['low_arr']
    volume_arr = indicators['volume_arr']

    dif = indicators['dif']
    dif_arr = indicators['dif_arr']
    bbi = indicators['bbi']
    前20日BBI = indicators['前20日BBI']

    知行短期趋势线 = indicators['知行短期趋势线']
    知行多空线 = indicators['知行多空线']

    知行短期趋势线_arr = []
    知行多空线_arr = []

    涨幅 = indicators['涨幅']
    振幅 = indicators['振幅']

    波幅 = indicators['波幅']
    prev_close = indicators['prev_close']
    波动率 = indicators['波动率']
    涨跌幅 = indicators['涨幅']
    大长阳 = indicators['大长阳']
    大长阴 = indicators['大长阴']
    参考成交量 = indicators['参考成交量']
    关键K = indicators['关键K']
    暴力K = indicators['暴力K']
    
    条件1得分 = 0.6 if dif >= 0 else 0
    条件2得分 = 0.3 if close > np.mean(close_arr[-60:]) else 0
    条件3得分 = 1.5 if -2 <= 涨幅 <= 1.8 else -3
    条件4得分 = 0.5 if 振幅 < 7 else -1
    条件5得分 = 0.8 if 振幅 < 4 else 0
    
    rsi_score = 0
    if indicators['rsi1'] < 20:
        rsi_score += 0.8
    if indicators['rsi1'] < 23:
        rsi_score += 0.7
    条件6得分 = rsi_score
    
    条件7得分 = 0
    if 知行短期趋势线 > close > 知行多空线:
        条件7得分 += 1.3
    if close < 知行多空线:
        条件7得分 -= 3
    if close * 1.003 < 知行多空线:    
        条件7得分 -= 3
    
    # 通达信条件8/9: IF(V=LLV(IF(一字涨停,10000000,V),N),得分,0)
    # 需要遍历历史每一天，判断是否一字涨停，是则用10000000替代
    def get_vol_with_yiziting(vol_arr, days):
        result = []
        code_prefix = code[:3]
        for i in range(days):
            if i < len(vol_arr):
                # 获取该天的O、H、C
                idx = len(vol_arr) - days + i
                if idx >= 0 and idx < len(open_arr) and idx < len(high_arr) and idx < len(close_arr):
                    o = open_arr[idx]
                    h = high_arr[idx]
                    c = close_arr[idx]
                    prev_close_i = close_arr[idx-1] if len(close_arr) > 1 else close_arr[idx]
                    if code_prefix in ['300', '688', '301']:
                        涨停价 = prev_close_i * 1.2
                    else:
                        涨停价 = prev_close_i * 1.1
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
    
    # vol_ma60 = np.mean(volume_arr[-60:])
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
        is_not_60_or_00 = not (str(indicators['code']).startswith('60') or str(indicators['code']).startswith('00'))
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
    知行多空线_arr = calculate_知行多空线_arr(close_arr, 114) if len(close_arr) >= 114 else []

    if 条件23得分 == 0:
        # 通达信公式: 知行线波动平均 := (REF(知行多空线,15)+REF(知行多空线,30)+REF(知行多空线,45)+REF(知行多空线,60))/4
        # 即15/30/45/60天前的知行多空线的平均值
        if len(知行多空线_arr) >= 61:
            知行线波动平均 = (知行多空线_arr[-16] + 知行多空线_arr[-31] + 
                            知行多空线_arr[-46] + 知行多空线_arr[-61]) / 4
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
    知行短期趋势线_arr = calculate_知行短期趋势线_arr(close_arr) if len(close_arr) >= 2 else []

    if len(close_arr) >= 2 and len(知行短期趋势线_arr) >= 2 and len(知行多空线_arr) >= 2:
        知行短期趋势线_prev = 知行短期趋势线_arr[-2]
        知行多空线_prev = 知行多空线_arr[-2]
    else:
        知行短期趋势线_prev = 知行短期趋势线
        知行多空线_prev = 知行多空线
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
    j_values = []
    prev_k = None
    prev_d = None
    for i in range(1, 21):
        if i < len(close_arr):
            low_9_i = np.min(low_arr[-9-i:-i]) if i < len(low_arr) else np.min(low_arr[-9:])
            high_9_i = np.max(high_arr[-9-i:-i]) if i < len(high_arr) else np.max(high_arr[-9:])
            close_i = close_arr[-i-1] if i < len(close_arr) else close_arr[-1]
            rsv_k_i = (close_i - low_9_i) / (high_9_i - low_9_i) * 100 if high_9_i != low_9_i else 50

            if prev_k is None:
                k_i = rsv_k_i
            else:
                k_i = (2.0 / 3.0) * prev_k + (1.0 / 3.0) * rsv_k_i
            
            if prev_d is None:
                d_i = k_i
            else:
                d_i = (2.0 / 3.0) * prev_d + (1.0 / 3.0) * k_i    

            prev_k = k_i
            prev_d = d_i

            j_i = 3 * k_i - 2 * d_i
            j_values.append(j_i)

    if len(j_values) >= 2:  # 至少要有前一日的J值
        # 从前一日开始往前找15天内的最高J值
        j_prev_list = j_values[-15:]  # 前一日J值的最后15个值
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
    
    条件35得分 = 1 if indicators['rsi2'] > indicators['rsi3'] and indicators['rsi3'] > indicators['rsi4'] else 0
    
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
    if open > 知行短期趋势线 and 知行短期趋势线 > 知行多空线 and close < 知行多空线 and close < open and volume > volume_arr[-1]:
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
    
    logger.info("=== B1各条件得分详情 ===")
    logger.info(f"股票代码code: {code}")
    logger.info(f"条件1得分(DIF>=0): {条件1得分}")
    logger.info(f"条件2得分(C>MA60): {条件2得分}")
    logger.info(f"条件3得分(涨幅-2~1.8): {条件3得分}")
    logger.info(f"条件4得分(振幅<7): {条件4得分}")
    logger.info(f"条件5得分(振幅<4): {条件5得分}")
    logger.info(f"条件6得分(RSI<20/23): {条件6得分}")
    logger.info(f"条件7得分(趋势线): {条件7得分}")
    logger.info(f"条件8得分(地量30-10天): {条件8得分}")
    logger.info(f"条件9得分(地量8-18天): {条件9得分}")
    logger.info(f"条件10得分(地量20天): {条件10得分}")
    logger.info(f"条件11得分(倍量+阳线): {条件11得分}")         
    logger.info(f"条件12得分(倍量+阴线): {条件12得分}")
    logger.info(f"条件13得分(近期倍量+阴线): {条件13得分}")
    logger.info(f"条件14得分(50/20日涨跌和): {条件14得分}")
    logger.info(f"条件15得分(涨跌量对比): {条件15得分}")
    logger.info(f"条件16得分(BBI>前20日BBI): {条件16得分}")
    logger.info(f"条件17得分(支撑位距离): {条件17得分}")
    logger.info(f"条件18得分(趋势线偏离): {条件18得分}")
    logger.info(f"条件19得分(创业板趋势线): {条件19得分}")
    logger.info(f"条件20得分(多空线偏离): {条件20得分}")
    logger.info(f"条件21得分(价格区间): {条件21得分}")
    logger.info(f"条件22得分(DIF背离): {条件22得分}")
    logger.info(f"条件23得分(放量上涨): {条件23得分}")
    logger.info(f"条件24得分(区间振幅): {条件24得分}")
    logger.info(f"条件25得分(跳空阳线): {条件25得分}")
    logger.info(f"条件26得分(知行线波动): {条件26得分}")
    logger.info(f"条件27得分(成交量变化): {条件27得分}")
    logger.info(f"条件28得分(趋势线下降): {条件28得分}")
    logger.info(f"条件29得分(十字星): {条件29得分}")
    logger.info(f"条件30得分(J值高位): {条件30得分}")
    logger.info(f"条件31得分(缩量连续下跌): {条件31得分}")
    logger.info(f"条件32得分(关键K): {条件32得分}")
    logger.info(f"条件33得分(连续大长阳): {条件33得分}")
    logger.info(f"条件34得分(大长阴): {条件34得分}")
    logger.info(f"条件35得分(RSI多头): {条件35得分}")
    logger.info(f"条件36得分(涨停次数): {条件36得分}")
    logger.info(f"条件37得分(开盘压制): {条件37得分}")
    logger.info(f"条件38得分(次高点): {条件38得分}")
    logger.info(f"条件39得分(无关键K): {条件39得分}")
    logger.info(f"\n>>> B1总分: {b1_score}")
    
    return b1_score
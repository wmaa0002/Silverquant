import os
import logging
from datetime import datetime
import numpy as np
from basic_module import calculate_知行多空线_arr
from basic_module import calculate_知行短期趋势线_arr
from basic_module import calculate_indicators


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

def calculate_b2_score(indicators):
    """
    计算B2得分系统
    B2触发条件: (REF(J,1)<=21 OR REF(RSI1,1)<=21) AND VOL>REF(VOL,1) AND 涨幅>3.95 AND VOL>VOL_MA60 AND C>O
    """
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


    vol_ma60 = indicators['vol_ma60']
    ma5 = indicators['ma5']
    ma10 = indicators['ma10']
    ma20 = indicators['ma20']
    ma50 = indicators['ma50']
    ma60 = indicators['ma60']
    ma14 = indicators['ma14']
    ma28 = indicators['ma28']
    ma57 = indicators['ma57']
    ma114 = indicators['ma114']
    ma3 = indicators['ma3']
    ma6 = indicators['ma6']
    ma12 = indicators['ma12']
    ma24 = indicators['ma24']

    k = indicators['k']
    d = indicators['d']
    j = indicators['j']
    rsi1 = indicators['rsi1']
    rsi2 = indicators['rsi2']
    rsi3 = indicators['rsi3']
    rsi4 = indicators['rsi4']
    
    # 计算前一日的J值和RSI1值
    if len(close_arr) >= 2:
        # 计算前一日的KDJ - 使用前一日的9日周期数据
        low_9_prev = np.min(low_arr[-10:]) if len(low_arr) >= 10 else np.min(low_arr)
        high_9_prev = np.max(high_arr[-10:]) if len(high_arr) >= 10 else np.max(high_arr)
        rsv_k_prev = (close_arr[-2] - low_9_prev) / (high_9_prev - low_9_prev) * 100 if high_9_prev != low_9_prev else 50
        k_prev = rsv_k_prev
        d_prev = k_prev
        j_prev = 3 * k_prev - 2 * d_prev
        
        # 计算前一日RSI1 (3日周期)
        gains_prev = []
        losses_prev = []
        for i in range(1, 4):  # RSI1使用3日周期
            if i < len(close_arr) - 1:
                diff = close_arr[-i-1] - close_arr[-i-2]
                gains_prev.append(max(diff, 0))
                losses_prev.append(max(-diff, 0))
        avg_gain_prev = np.mean(gains_prev) if gains_prev else 0
        avg_loss_prev = np.mean(losses_prev) if losses_prev else 0.001
        rs_prev = avg_gain_prev / avg_loss_prev
        rsi1_prev = 100 - (100 / (1 + rs_prev))
    else:
        j_prev = j
        rsi1_prev = rsi1
    
    # B2触发条件 - 使用前一日的J值和RSI1值
    B2触发 = (j_prev <= 21 or rsi1_prev <= 21) and volume > volume_arr[-2] if len(volume_arr) > 1 else False
    B2触发 = B2触发 and 涨幅 > 3.95 and volume > vol_ma60 and close > open
    
    if not B2触发:
        return 0
    
    # ===== 计算得分1-31 =====
    
    # 得分1: IF(J>80,-3,0) + IF(J>65,-0.8,0) + IF(J>55,-0.8,0)
    得分1 = 0
    if j > 80:
        得分1 -= 3
    if j > 65:
        得分1 -= 0.8
    if j > 55:
        得分1 -= 0.8
    
    # 得分2: IF(DIF>=0,0.3,0)
    得分2 = 0.3 if dif >= 0 else 0
    
    # 得分3: IF(MA10>REF(MA10,1) AND MA20>REF(MA20,1) AND MA50>REF(MA50,1),0.6,0)
    得分3 = 0
    if len(close_arr) >= 2:
        ma10_prev = np.mean(close_arr[-11:-1]) if len(close_arr) >= 11 else ma10
        ma20_prev = np.mean(close_arr[-21:-1]) if len(close_arr) >= 21 else ma20
        ma50_prev = np.mean(close_arr[-51:-1]) if len(close_arr) >= 51 else ma50
        if ma10 > ma10_prev and ma20 > ma20_prev and ma50 > ma50_prev:
            得分3 = 0.6
    
    # 得分4: IF(C>知行多空线,0.3,0)
    得分4 = 0.3 if close > 知行多空线 else 0
    
    # 得分5: IF(NOT(J<K AND J<D),0.3,0) 即 J>=K OR J>=D
    得分5 = 0.3 if not (j < k and j < d) else 0
    
    # 得分6: IF(C>BBI,0.4,0)
    得分6 = 0.4 if close > bbi else 0
    
    # 得分7: IF(RSI1>枢轴线,0.5,0) + IF(RSI1>枢轴线-5,0.3,2)
    # 枢轴线:=MA(RSI1,25) - 需要计算过去25日的RSI1均值
    # 计算历史RSI1序列
    rsi1_history = []
    for idx in range(min(25, len(close_arr)-1)):
        if idx < len(close_arr) - 1:
            gains_rsi = []
            losses_rsi = []
            for i in range(1, min(4, idx+2)):  # RSI1使用3日周期
                if i < len(close_arr) - idx - 1:
                    diff = close_arr[-i-idx-1] - close_arr[-i-idx-2]
                    gains_rsi.append(max(diff, 0))
                    losses_rsi.append(max(-diff, 0))
            if gains_rsi and losses_rsi:
                avg_gain_rsi = np.mean(gains_rsi)
                avg_loss_rsi = np.mean(losses_rsi) if np.mean(losses_rsi) != 0 else 0.001
                rs_rsi = avg_gain_rsi / avg_loss_rsi
                rsi_val = 100 - (100 / (1 + rs_rsi))
                rsi1_history.append(rsi_val)
    枢轴线 = np.mean(rsi1_history) if rsi1_history else rsi1
    得分7 = 0
    if rsi1 > 枢轴线:
        得分7 += 0.5
    if rsi1 > 枢轴线 - 5:
        得分7 += 0.3
    
    # 得分8: 上影线相关
    # 修正: K线长度 = HIGH - LOW (最高价 - 最低价)
    K线长度 = high - low
    上影线 = high - max(close, open)
    得分8 = 0
    if K线长度 > 0:
        if 上影线 <= K线长度 / 4:
            得分8 += 1.5
        if 上影线 >= K线长度 / 4:
            得分8 -= 1
        if 上影线 >= K线长度 / 2:
            得分8 -= 1
    
    # 得分9: 上影线<=K线长度/4 AND 下影线<=K线长度/4 AND C>O
    下影线 = min(close, open) - low
    得分9 = 0
    if K线长度 > 0:
        if 上影线 <= K线长度 / 4 and 下影线 <= K线长度 / 4 and close > open:
            得分9 = 1.2
    
    # 得分10: VOL > VOL_MA60, 1.25*VOL_MA60, 1.5*VOL_MA60
    得分10 = 0
    if volume > vol_ma60:
        得分10 += 0.4
    if volume > 1.25 * vol_ma60:
        得分10 += 0.6
    if volume > 1.5 * vol_ma60:
        得分10 += 0.8
    
    # 得分11: C=HHV(C,90), HHV(C,60), HHV(C,30)
    得分11 = 0
    if len(close_arr) >= 90:
        if close >= np.max(close_arr[-90:]):
            得分11 += 0.7
    if len(close_arr) >= 60:
        if close >= np.max(close_arr[-60:]):
            得分11 += 0.7
    if len(close_arr) >= 30:
        if close >= np.max(close_arr[-30:]):
            得分11 += 0.7
    
    # 得分12: 阳量40日总和 vs 阴量40日总和
    阳量40日总和 = np.sum(np.where(close_arr[-40:] > open_arr[-40:], volume_arr[-40:], 0))
    阴量40日总和 = np.sum(np.where(close_arr[-40:] < open_arr[-40:], volume_arr[-40:], 0))
    得分12 = 0
    if 阳量40日总和 > 阴量40日总和:
        得分12 += 0.3
    if 阳量40日总和 >= 1.25 * 阴量40日总和:
        得分12 += 0.4
    if 阳量40日总和 >= 1.5 * 阴量40日总和:
        得分12 += 0.5
    
    # 得分13: 最大阳量20日 > 最大阴量20日
    最大阳量20日 = np.max(np.where(close_arr[-20:] > open_arr[-20:], volume_arr[-20:], 0))
    最大阴量20日 = np.max(np.where(close_arr[-20:] < open_arr[-20:], volume_arr[-20:], 0))
    得分13 = 0.5 if 最大阳量20日 > 最大阴量20日 else 0
    
    # 得分14: REF(C,1)<REF(知行多空线,1) AND C>知行多空线 AND C>REF(H,1)
    得分14 = 0
    if len(close_arr) >= 2 and len(知行多空线_arr) >= 2:
        if close_arr[-2] < 知行多空线_arr[-2] and close > 知行多空线 and close > high_arr[-2]:
            得分14 = 0.5
    
    # 得分15: 价格高点位置相关
    价格高点位置 = 0
    if len(high_arr) >= 30:
        hhv_30 = np.max(high_arr[-30:])
        for idx in range(len(high_arr) - 1, len(high_arr) - 31, -1):
            if high_arr[idx] >= hhv_30:
                价格高点位置 = len(high_arr) - idx - 1
                break
    
    得分15 = 0
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
            得分15 -= 0.3
        if 高点DIF < 前15高DIF:
            得分15 -= 0.3
    
    # 得分16: 成交量高点+阳线
    得分16 = 0
    for days, points in [(60, 0.3), (50, 0.3), (40, 0.3)]:
        if len(volume_arr) >= days:
            hhv_vol_days = np.max(volume_arr[-days:])
            barslast_hhv = 0
            for idx in range(len(volume_arr) - 1, len(volume_arr) - days - 1, -1):
                if volume_arr[idx] >= hhv_vol_days:
                    barslast_hhv = len(volume_arr) - idx - 1
                    break
            if barslast_hhv >= 1 and barslast_hhv < len(close_arr) and barslast_hhv < len(open_arr):
                if close_arr[-barslast_hhv-1] > open_arr[-barslast_hhv-1]:
                    得分16 += points
    
    # 得分17: 近期成交量高点+阳线/阴线
    得分17 = 0
    for days, points in [(30, 0.3), (20, 0.3), (10, 0.3)]:
        if len(volume_arr) >= days:
            hhv_vol_days = np.max(volume_arr[-days:])
            barslast_hhv = 0
            for idx in range(len(volume_arr) - 1, len(volume_arr) - days - 1, -1):
                if volume_arr[idx] >= hhv_vol_days:
                    barslast_hhv = len(volume_arr) - idx - 1
                    break
            if barslast_hhv >= 1 and barslast_hhv < len(close_arr) and barslast_hhv < len(open_arr):
                if close_arr[-barslast_hhv-1] > open_arr[-barslast_hhv-1]:
                    得分17 += points
                else:
                    得分17 -= 2.5
    
    # 得分18: 上证指数相关（简化处理，假设总是满足部分条件）
    得分18 = 0.3  # 简化处理
    
    # 得分19: 成交量放大倍数
    # 修正: 参考成交量:=IF(REF(VOL,1)<=VOL/8,REF(VOL,2),REF(VOL,1))
    if len(volume_arr) >= 2:
        if volume_arr[-1] <= volume / 8:
            参考成交量 = volume_arr[-2] if len(volume_arr) > 2 else volume
        else:
            参考成交量 = volume_arr[-1]
    else:
        参考成交量 = volume
    得分19 = 0
    if volume > 参考成交量 * 1.8:
        得分19 += 0.8
    if volume > 参考成交量 * 2.5:
        得分19 += 0.3
    if volume > 参考成交量 * 3:
        得分19 += 0.3
    if volume > 参考成交量 * 3.5:
        得分19 += 0.3
    if volume > 参考成交量 * 4:
        得分19 += 0.3
    
    # 得分20: 关键K
    # 修正: 波幅使用正确的TR(True Range)公式
    # TR = MAX(HIGH-LOW, ABS(HIGH-REF(CLOSE,1)), ABS(LOW-REF(CLOSE,1)))
    tr_values = []
    for i in range(min(30, len(close_arr)-1)):
        high_i = high_arr[-i-1] if i < len(high_arr) else high
        low_i = low_arr[-i-1] if i < len(low_arr) else low
        close_prev = close_arr[-i-2] if i+1 < len(close_arr) else close_arr[-1]
        tr1 = high_i - low_i
        tr2 = abs(high_i - close_prev)
        tr3 = abs(low_i - close_prev)
        tr_values.append(max(tr1, tr2, tr3))
    波幅 = np.mean(tr_values) if tr_values else 0
    涨跌幅 = 涨幅
    大长阳 = close > open and 涨跌幅 > 波幅 / prev_close * 100 * 1.5 and 涨跌幅 > 2
    关键K = close > close_arr[-2] and volume > 参考成交量 * 1.8 and 大长阳 and volume > np.mean(volume_arr[-40:]) if len(volume_arr) >= 40 else False
    得分20 = 1 if 关键K else 0
    
    # 得分21: 关键K AND 暴力K
    暴力K = close > close_arr[-2] and volume > 参考成交量 * 1.8 and 涨跌幅 > 4 and 上影线 <= K线长度 / 4 and volume > np.mean(volume_arr[-60:]) if len(volume_arr) >= 60 else False
    得分21 = 0.5 if 关键K and 暴力K else 0
    
    # 得分22: RSI多头排列
    得分22 = 0.7 if rsi2 > rsi3 and rsi3 > rsi4 else 0
    
    # 得分23: 缩量连续下跌
    得分23 = 0
    if len(volume_arr) >= 5:
        if (volume < volume_arr[-1] * 1.1 and volume_arr[-1] < volume_arr[-2] * 1.1 and 
            volume_arr[-2] < volume_arr[-3] * 1.1 and volume_arr[-3] < volume_arr[-4] * 1.1):
            if (close_arr[-1] < open_arr[-1] and close_arr[-2] < open_arr[-2] and 
                close_arr[-3] < open_arr[-3] and close_arr[-4] < open_arr[-4]):
                得分23 = -1
    
    # 得分24: 成交量创60日最高
    得分24 = 0
    for days in [60, 50, 40, 30]:
        if len(volume_arr) >= days:
            if volume >= np.max(volume_arr[-days:]):
                得分24 += 0.5
    
    # 得分25: J值上升
    # 修正: 比较J值而非收盘价
    # IF(J>REF(J,1) AND REF(J,1)<REF(J,2), 0.5, 0)
    得分25 = 0
    if len(close_arr) >= 3:
        # 需要计算前两日的J值
        j_prev = j  # 当前J值(在调用前已计算)
        # 计算前一日J值
        low_9_1 = np.min(low_arr[-10:-1]) if len(low_arr) >= 10 else np.min(low_arr)
        high_9_1 = np.max(high_arr[-10:-1]) if len(high_arr) >= 10 else np.max(high_arr)
        rsv_k_1 = (close_arr[-2] - low_9_1) / (high_9_1 - low_9_1) * 100 if high_9_1 != low_9_1 else 50
        k_1 = rsv_k_1
        d_1 = k_1
        j_1 = 3 * k_1 - 2 * d_1
        # 计算前两日J值
        low_9_2 = np.min(low_arr[-11:-2]) if len(low_arr) >= 11 else np.min(low_arr)
        high_9_2 = np.max(high_arr[-11:-2]) if len(high_arr) >= 11 else np.max(high_arr)
        rsv_k_2 = (close_arr[-3] - low_9_2) / (high_9_2 - low_9_2) * 100 if high_9_2 != low_9_2 else 50
        k_2 = rsv_k_2
        d_2 = k_2
        j_2 = 3 * k_2 - 2 * d_2
        # J值拐点: 今日上升且昨日下降
        if j_prev > j_1 and j_1 < j_2:
            得分25 = 0.5
    
    # 得分26: 大长阴
    # 实现: 15/10日内出现放量长阴，根据放量程度扣分
    # IF(COUNT(大长阴 AND VOL > REF(VOL, 1) * 1.2 AND VOL > MA(VOL, 60) AND VOL > (HHV(VOL, 60))/1.95, 15) >= 1, -0.4, 0) + ...
    得分26 = 0
    # 计算大长阴: C<O AND ABS(涨跌幅)>波动率*1.1 AND ABS(涨跌幅)>2
    波幅_temp = np.mean(np.abs(high_arr[-30:] - low_arr[-30:])) if len(high_arr) >= 30 else 0
    vol_ma60_val = np.mean(volume_arr[-60:]) if len(volume_arr) >= 60 else np.mean(volume_arr)
    hhv_vol_60 = np.max(volume_arr[-60:]) if len(volume_arr) >= 60 else np.max(volume_arr)
    
    # 检查15日内
    for days_back, threshold in [(15, 1.2), (10, 1.4), (10, 1.6), (10, 1.8), (10, 2.0)]:
        count = 0
        for i in range(1, min(days_back + 1, len(close_arr))):
            if i < len(close_arr) and i < len(open_arr) and i < len(volume_arr) and i < len(high_arr) and i < len(low_arr):
                prev_close_i = close_arr[-i-1]
                if prev_close_i > 0:
                    涨跌幅_i = (close_arr[-i-1] - open_arr[-i-1]) / prev_close_i * 100
                    波幅_i = (high_arr[-i-1] - low_arr[-i-1]) / prev_close_i * 100 if prev_close_i > 0 else 0
                    # 大长阴条件
                    is_big_down = (close_arr[-i-1] < open_arr[-i-1] and 
                                abs(涨跌幅_i) > 波幅_i * 1.1 and 
                                abs(涨跌幅_i) > 2)
                    # 放量条件
                    is_high_vol = volume_arr[-i-1] > volume_arr[-i-2] * threshold if i < len(volume_arr) - 1 else False
                    is_active = volume_arr[-i-1] > vol_ma60_val
                    is_high_relative = volume_arr[-i-1] > hhv_vol_60 / 1.95
                    if is_big_down and is_high_vol and is_active and is_high_relative:
                        count += 1
        if count >= 1:
            得分26 -= 0.4
    
    # 得分27: 成交量低于近期高点
    得分27 = 0
    for days in [13, 12, 11]:
        if len(volume_arr) >= days:
            if volume < np.max(volume_arr[-days:]):
                得分27 -= 0.3
    
    # 得分28: 十字星
    得分28 = 0
    十字星_count = 0
    for i in range(60):
        if i < len(close_arr) - 1:
            if close_arr[-i-1] == open_arr[-i-1] and (close_arr[-i-1] != close_arr[-i-2] * 1.1 or close_arr[-i-1] <= close_arr[-i-2]):
                十字星_count += 1
    if 十字星_count > 2:
        得分28 = -1.5
    
    # 得分29: 低量周期
    # 实现: 3日内出现阶段地量，得1分
    # 条件8得分: V=LLV(30/26/24/22/20日内最低量)
    # 条件9得分: V=LLV(18/16/14/12/10日内最低量)
    条件8得分 = 0
    for days_llv in [30, 26, 24, 22, 20]:
        if len(volume_arr) >= days_llv:
            llv_vol = np.min(volume_arr[-days_llv:])
            if volume <= llv_vol:
                条件8得分 += 0.3
    条件9得分 = 0
    for days_llv in [18, 16, 14, 12, 10]:
        if len(volume_arr) >= days_llv:
            llv_vol = np.min(volume_arr[-days_llv:])
            if volume <= llv_vol:
                条件9得分 += 0.3
    # 3日内出现阶段地量
    得分29 = 0
    if 条件8得分 > 0 or 条件9得分 > 0:
        得分29 = 1
    
    # 得分30: 趋势线相关
    # 修正: REF(C,10)是前11天的收盘价, REF(知行短期趋势线,10)是前11天的值
    # IF(REF(C,10) > REF(知行短期趋势线,10) AND ABS((REF(L,1)/REF(知行多空线,1))-1) <= 0.02, 1, 0)
    得分30 = 0
    if len(close_arr) >= 11 and len(知行短期趋势线_arr) >= 11 and len(知行多空线_arr) >= 2:
        # REF(C,10) = close_arr[-11] (11天前)
        ref_c_10 = close_arr[-11] if len(close_arr) >= 11 else close
        # REF(知行短期趋势线,10) = 知行短期趋势线_arr[-11]
        ref_知行短期趋势线_10 = 知行短期趋势线_arr[-11] if len(知行短期趋势线_arr) >= 11 else 知行短期趋势线
        # REF(L,1) = low_arr[-1] (昨日最低价)
        ref_l_1 = low_arr[-1] if len(low_arr) >= 1 else low
        # REF(知行多空线,1) = 知行多空线_arr[-1]
        ref_知行多空线_1 = 知行多空线_arr[-1] if len(知行多空线_arr) >= 1 else 知行多空线
        
        if ref_c_10 > ref_知行短期趋势线_10:
            if ref_知行多空线_1 > 0 and abs((ref_l_1 / ref_知行多空线_1) - 1) <= 0.02:
                得分30 = 1
    
    # 得分31: 反包K线
    得分31 = 0
    if len(close_arr) >= 2:
        if close_arr[-1] < open_arr[-1] and low < low_arr[-2] and close > high_arr[-2]:
            得分31 = 1
    
    # 计算总分
    b2_score = (得分1 + 得分2 + 得分3 + 得分4 + 得分5 + 得分6 + 得分7 + 得分8 + 得分9 + 得分10 +
            得分11 + 得分12 + 得分13 + 得分14 + 得分15 + 得分16 + 得分17 + 得分18 + 得分19 +
            得分20 + 得分21 + 得分22 + 得分23 + 得分24 + 得分25 + 得分26 + 得分27 + 得分28 +
            得分29 + 得分30 + 得分31)
    
    logger.info(f"\n=== B2各条件得分详情 ===")
    logger.info(f"B2触发: {B2触发}")
    logger.info(f"得分1(J值): {得分1}")
    logger.info(f"得分2(DIF>=0): {得分2}")
    logger.info(f"得分3(均线多头): {得分3}")
    logger.info(f"得分4(C>知行多空线): {得分4}")
    logger.info(f"得分5(KDJ): {得分5}")
    logger.info(f"得分6(C>BBI): {得分6}")
    logger.info(f"得分7(RSI): {得分7}")
    logger.info(f"得分8(上影线): {得分8}")
    logger.info(f"得分9(上下影线): {得分9}")
    logger.info(f"得分10(成交量): {得分10}")
    logger.info(f"得分11(高点): {得分11}")
    logger.info(f"得分12(阳量): {得分12}")
    logger.info(f"得分13(最大阳量): {得分13}")
    logger.info(f"得分14(突破): {得分14}")
    logger.info(f"得分15(DIF背离): {得分15}")
    logger.info(f"得分16(量能高点): {得分16}")
    logger.info(f"得分17(近期量能): {得分17}")
    logger.info(f"得分18(上证): {得分18}")
    logger.info(f"得分19(放量): {得分19}")
    logger.info(f"得分20(关键K): {得分20}")
    logger.info(f"得分21(暴力K): {得分21}")
    logger.info(f"得分22(RSI多头): {得分22}")
    logger.info(f"得分23(缩量下跌): {得分23}")
    logger.info(f"得分24(量能新高): {得分24}")
    logger.info(f"得分25(J上升): {得分25}")
    logger.info(f"得分26(大长阴): {得分26}")
    logger.info(f"得分27(低量能): {得分27}")
    logger.info(f"得分28(十字星): {得分28}")
    logger.info(f"得分29(条件8/9): {得分29}")
    logger.info(f"得分30(趋势线): {得分30}")
    logger.info(f"得分31(反包): {得分31}")
    logger.info(f"\n>>> B2总分: {b2_score}")
   
    return b2_score
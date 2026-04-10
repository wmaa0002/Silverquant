import os
import sys

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd

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

def calculate_kdj(close_arr, high_arr, low_arr, n=9, m1=3, m2=3):
    """计算KDJ指标"""
    k_arr = []
    d_arr = []
    j_arr = []
    
    for i in range(len(close_arr)):
        # 取最近n天的最低价和最高价
        start = max(0, i - n + 1)
        low_n = np.min(low_arr[start:i+1])
        high_n = np.max(high_arr[start:i+1])
        
        # 计算RSV
        if high_n != low_n:
            rsv = (close_arr[i] - low_n) / (high_n - low_n) * 100
        else:
            rsv = 50
        
        # 计算K、D
        if i == 0:
            k = rsv
            d = rsv
        else:
            k = (2/3) * k_arr[-1] + (1/3) * rsv
            d = (2/3) * d_arr[-1] + (1/3) * k
        
        j = 3 * k - 2 * d
        
        k_arr.append(k)
        d_arr.append(d)
        j_arr.append(j)
    
    return k_arr[-1], d_arr[-1], j_arr[-1]

def calculate_知行多空线_arr(close_arr: np.ndarray, require_min_days: int = 114) -> np.ndarray:
    """
    计算知行多空线数组
    
    Args:
        close_arr: 收盘价数组（升序，从最早到今天）
        require_min_days: 需要的最小天数（默认114天）
    
    Returns:
        np.ndarray: 知行多空线数组
    """
    n = len(close_arr)
    
    # 需要至少114天数据才能准确计算
    if n < require_min_days:
        # 数据不足时返回空数组或用可用数据计算
        return np.array([])
    
    知行多空线_arr = []
    
    for i in range(n):
        # 第i天（从0开始）
        
        # MA14: 最近14天收盘价均值
        if i >= 13:  # 需要至少14天数据
            ma14 = np.mean(close_arr[i-13:i+1])
        else:
            ma14 = np.mean(close_arr[:i+1])
        
        # MA28: 最近28天收盘价均值
        if i >= 27:
            ma28 = np.mean(close_arr[i-27:i+1])
        else:
            ma28 = np.mean(close_arr[:i+1])
        
        # MA57: 最近57天收盘价均值
        if i >= 56:
            ma57 = np.mean(close_arr[i-56:i+1])
        else:
            ma57 = np.mean(close_arr[:i+1])
        
        # MA114: 最近114天收盘价均值
        if i >= 113:
            ma114 = np.mean(close_arr[i-113:i+1])
        else:
            ma114 = np.mean(close_arr[:i+1])
        
        # 知行多空线
        知行多空线 = (ma14 + ma28 + ma57 + ma114) / 4
        知行多空线_arr.append(知行多空线)
    
    return np.array(知行多空线_arr)

def calculate_知行短期趋势线_arr(close_arr: np.ndarray) -> np.ndarray:
    """
    计算知行短期趋势线数组（EMA10的EMA10）
    
    Args:
        close_arr: 收盘价数组（升序）
    
    Returns:
        np.ndarray: 知行短期趋势线数组
    """
    n = len(close_arr)
    知行短期趋势线_arr = []
    
    for i in range(n):
        # 第i天（从0开始）
        
        # ====== 第一步：计算第i天的EMA10 ======
        # EMA_today = EMA_yesterday * (10-1)/10 + close_today * 1/10
        #       = EMA_yesterday * 0.9 + close_today * 0.1
        
        if i == 0:
            # 第一天：EMA10 = 当天收盘价
            ema10_i = close_arr[0]
        else:
            # 计算到第i天为止的EMA10
            ema10_i = close_arr[i]
            for j in range(i):
                # 从第0天到第i天，用EMA公式迭代
                alpha = 1 / 10  # 2/(N+1) = 2/11 ≈ 0.0909
                ema10_i = ema10_i * (1 - alpha) + close_arr[i - j] * alpha
        
        # ====== 第二步：计算EMA10的EMA10 ======
        if i == 0:
            # 第一天：知行短期趋势线 = EMA10
            知行趋势线_i = ema10_i
        else:
            # 需要用之前每天的EMA10来计算
            # 先计算所有历史EMA10
            ema10_history = []
            for k in range(i + 1):
                ema10_k = close_arr[k]
                for j in range(k):
                    alpha = 1 / 10
                    ema10_k = ema10_k * (1 - alpha) + close_arr[k - j] * alpha
                ema10_history.append(ema10_k)
            
            # 再对EMA10序列计算EMA10
            知行趋势线_i = ema10_history[i]
            for m in range(i):
                alpha = 1 / 10
                知行趋势线_i = 知行趋势线_i * (1 - alpha) + ema10_history[i - m - 1] * alpha
        
        知行短期趋势线_arr.append(知行趋势线_i)
    
    return np.array(知行短期趋势线_arr)

def calculate_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """计算技术指标"""
    code = df['code'].values[0]
    close_arr = df['close'].values
    open_arr = df['open'].values
    high_arr = df['high'].values
    low_arr = df['low'].values
    volume_arr = df['volume'].values
    volume_arr = np.nan_to_num(volume_arr, nan=0)

    close = close_arr[-1]
    open = open_arr[-1]
    high = high_arr[-1]
    low = low_arr[-1]
    volume = volume_arr[-1]

    n = len(close_arr)
    
    # 基础数据
    prev_close = close_arr[-2] if n >= 2 else close_arr[-1]
    涨幅 = (close_arr[-1] - prev_close) / prev_close * 100 if prev_close != 0 else 0
    振幅 = (high_arr[-1] - low_arr[-1]) / prev_close * 100 if prev_close != 0 else 0


    波幅 = np.mean(np.abs(high_arr[-30:] - low_arr[-30:]))
    prev_close = close_arr[-2] if len(close_arr) >= 2 else close_arr[-1]
    波动率 = 波幅 / prev_close * 100 if prev_close != 0 else 0
    涨跌幅 = (close - prev_close) / prev_close * 100 if prev_close != 0 else 0
    大长阳 = close > open and 涨跌幅 > 波动率 * 1.5 and 涨跌幅 > 2
    大长阴 = close < open and abs(涨跌幅) > 波动率 * 1.1 and abs(涨跌幅) > 2
    参考成交量 = volume_arr[-2] if volume_arr[-1] <= volume / 8 else volume_arr[-1]
    关键K = close > close_arr[-2] and volume > 参考成交量 * 1.8 and 大长阳 and volume > np.mean(volume_arr[-40:]) if len(volume_arr) >= 40 else False
    暴力K = close > close_arr[-2] and volume > 参考成交量 * 1.8 and 涨跌幅 > 4 and (high - max(close, open)) <= (high - open) / 4 and volume > np.mean(volume_arr[-60:]) if len(volume_arr) >= 60 else False
    
    # 均线
    ma5 = np.mean(close_arr[-5:]) 
    ma10 = np.mean(close_arr[-10:]) 
    ma14 = np.mean(close_arr[-14:]) 
    ma20 = np.mean(close_arr[-20:]) 
    ma28 = np.mean(close_arr[-28:]) 
    ma30 = np.mean(close_arr[-30:]) 
    ma50 = np.mean(close_arr[-50:]) 
    ma57 = np.mean(close_arr[-57:]) 
    ma60 = np.mean(close_arr[-60:]) 
    ma114 = np.mean(close_arr[-114:]) 

    ma3 = np.mean(close_arr[-3:])
    ma6 = np.mean(close_arr[-6:])
    ma12 = np.mean(close_arr[-12:])
    ma24 = np.mean(close_arr[-24:])
    
    
    # 成交量均线
    vol_ma5 = np.mean(volume_arr[-5:]) if n >= 5 else volume_arr[-1]
    vol_ma10 = np.mean(volume_arr[-10:]) if n >= 10 else volume_arr[-1]
    vol_ma20 = np.mean(volume_arr[-20:]) if n >= 20 else volume_arr[-1]
    vol_ma60 = np.mean(volume_arr[-60:]) if n >= 60 else volume_arr[-1]
    
    # MACD (DIF)
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
    
    # 知行短期趋势线
    ema10_1 = close_arr[-1]
    for i in range(2, 11):
        if i < len(close_arr):
            ema10_1 = ema10_1 * (2/11) + close_arr[-i] * (1 - 2/11)
    ema10_2 = ema10_1
    for i in range(2, 11):
        if i < len(close_arr):
            ema10_2 = ema10_2 * (2/11) + ema10_1 * (1 - 2/11)
    知行短期趋势线 = ema10_2
    
    # 知行多空线
    知行多空线 = (ma14 + ma28 + ma57 + ma114) / 4
    
    # DEA
    dea = 0
    
    # KDJ
    k, d, j = calculate_kdj(close_arr, high_arr, low_arr)
    
    # RSI
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
    
    # BBI
    bbi = (ma3 + ma6 + ma12 + ma24) / 4
    
    # 通达信公式: 前20日BBI:=REF(BBI,20) - 20天前的BBI值
    if len(close_arr) >= 21:
        ma3_20 = np.mean(close_arr[-23:-20]) if len(close_arr) >= 23 else close_arr[-1]
        ma6_20 = np.mean(close_arr[-26:-20]) if len(close_arr) >= 26 else close_arr[-1]
        ma12_20 = np.mean(close_arr[-32:-20]) if len(close_arr) >= 32 else close_arr[-1]
        ma24_20 = np.mean(close_arr[-44:-20]) if len(close_arr) >= 44 else close_arr[-1]
        前20日BBI = (ma3_20 + ma6_20 + ma12_20 + ma24_20) / 4
    else:
        前20日BBI = bbi
    
    
    return {
        'code': code,

        'open_arr': open_arr,
        'high_arr': high_arr,
        'low_arr': low_arr,
        'close_arr': close_arr,
        'volume_arr': volume_arr,
        
        'open': float(open),
        'high': float(high),
        'low': float(low),
        'close': float(close),
        'volume': float(volume),
        'prev_close': float(prev_close),

        '涨幅': float(涨幅),
        '振幅': float(振幅),

        '波幅': float(波幅),
        '波动率': float(波动率),
        '涨幅': float(涨幅),    
        '大长阳': float(大长阳),
        '大长阴': float(大长阴),
        '参考成交量': float(参考成交量),
        '关键K': float(关键K),
        '暴力K': float(暴力K),

        'ma5': float(ma5),
        'ma10': float(ma10),
        'ma14': float(ma14),
        'ma20': float(ma20),
        'ma28': float(ma28),
        'ma30': float(ma30),
        'ma50': float(ma50),
        'ma57': float(ma57),
        'ma60': float(ma60),
        'ma114': float(ma114),
        'ma3': float(ma3),
        'ma6': float(ma6),
        'ma12': float(ma12),
        'ma24': float(ma24),

        'dif': float(dif),
        'dif_arr': dif_arr,
        'dea': float(dea),

        'k': float(k),
        'd': float(d),
        'j': float(j),

        'rsi1': float(rsi1),
        'rsi2': float(rsi2),
        'rsi3': float(rsi3),
        'rsi4': float(rsi4),

        'bbi': float(bbi),
        '前20日BBI': float(前20日BBI),
        
        '知行短期趋势线': float(知行短期趋势线),
        '知行多空线': float(知行多空线),

        'vol_ma5': float(vol_ma5),
        'vol_ma10': float(vol_ma10),
        'vol_ma20': float(vol_ma20),
        'vol_ma60': float(vol_ma60),
    }
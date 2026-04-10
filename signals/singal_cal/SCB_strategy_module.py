import os
import logging
from datetime import datetime
import numpy as np
from basic_module import calculate_知行多空线_arr


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


def calculate_dl_score(indicators):
    """计算地量等级"""

    code = indicators['code']
    close = indicators['close']
    high = indicators['high']
    low = indicators['low']
    open_price = indicators['open']
    close_arr = indicators['close_arr']
    high_arr = indicators['high_arr']
    low_arr = indicators['low_arr']
    volume_arr = indicators['volume_arr']
    volume = indicators['volume']
    prev_close = indicators['prev_close']

    code_prefix = code[:3]
    if code_prefix in ['300', '688', '301']:
        涨停价 = prev_close * 1.2
        跌停价 = prev_close * 0.8
    else:
        涨停价 = prev_close * 1.1
        跌停价 = prev_close * 0.9
    
    涨停板 = (close >= 涨停价) and (close > open_price)
    跌停板 = (close <= 跌停价) and (close < open_price)
    一字涨停 = (open_price == close) and (close == high) and (close >= 涨停价)
    一字跌停 = (open_price == close) and (close == low) and (close <= 跌停价)
    跌停板 = (close <= 跌停价 * 1.01) and (close < open_price)
    一字涨停 = (open_price == close) and (close == high) and (close >= 涨停价 * 0.99)
    一字跌停 = (open_price == close) and (close == low) and (close <= 跌停价 * 1.01)
    
    if 涨停板 or 跌停板 or 一字涨停 or 一字跌停:
        return 0
    
    地量1 = 0
    for days in range(10, 21):
        if len(volume_arr) >= days:
            llv_vol = np.min(volume_arr[-days:])
            if volume * 0.9 <= llv_vol:
                地量1 = days
                break
    
    地量2 = 0
    for days in range(21, 31):
        if len(volume_arr) >= days:
            llv_vol = np.min(volume_arr[-days:])
            if volume * 0.9 <= llv_vol:
                地量2 = days
                break
    
    地量3 = 0
    for days in range(31, 41):
        if len(volume_arr) >= days:
            llv_vol = np.min(volume_arr[-days:])
            if volume * 0.9 <= llv_vol:
                地量3 = days
                break
    
    地量4 = 0
    for days in range(41, 51):
        if len(volume_arr) >= days:
            llv_vol = np.min(volume_arr[-days:])
            if volume * 0.9 <= llv_vol:
                地量4 = days
                break
    
    地量等级 = 0
    if 地量4 >= 41:
        地量等级 = 地量4
    elif 地量3 >= 31:
        地量等级 = 地量3
    elif 地量2 >= 21:
        地量等级 = 地量2
    elif 地量1 >= 10:
        地量等级 = 地量1
    
    return 地量等级

def check_dl_basic_condition(indicators, X=30):

    """
    检查地量基础条件（完全还原通达信公式）
    
    地量基础条件:
    地量>=X AND 非ST股 AND FINANCE(42)>100 AND VOL>0 
    AND 前60日非阴 AND (COUNT(关键K,60)>=1 OR COUNT(暴力K,60)>=1) AND 异动80
    """
    close = indicators['close']
    high = indicators['high']
    low = indicators['low']
    open_price = indicators['open']
    close_arr = indicators['close_arr']
    open_arr = indicators['open_arr']
    high_arr = indicators['high_arr']
    low_arr = indicators['low_arr']
    volume_arr = indicators['volume_arr']
    volume = indicators['volume']
    prev_close = indicators['prev_close']

    st_days = indicators['code'].startswith('ST') or '*ST' in indicators['code']

    # 1. 地量>=X
    dl_score = calculate_dl_score(indicators)
    if dl_score < X:
        return False
    
    # 2. 非ST股
    if st_days:
        return False
    
    # 3. VOL>0
    if volume <= 0:
        return False
    
    # 4. 前60日非阴: REF(C,HHVBARS(VOL,60))>=REF(O,HHVBARS(VOL,60))
    if len(volume_arr) >= 60:
        # 找到60日最大量的位置
        hhv_vol_idx = np.argmax(volume_arr[-60:])
        # 该位置的开盘和收盘
        open_at_hhv = open_arr[-60 + hhv_vol_idx]
        close_at_hhv = close_arr[-60 + hhv_vol_idx]
        # 如果最大量当天是阴线，则不满足
        if close_at_hhv < open_at_hhv:
            return False
    
    # 5. COUNT(关键K,60)>=1 OR COUNT(暴力K,60)>=1
    has_keyK_or_blk = False
    for i in range(60):
        if i < len(volume_arr) - 1:
            # 关键K: CLOSE>REF(CLOSE,1) AND VOL>参考成交量*1.8 AND 大长阳 AND VOL>MA(VOL,40)
            prev_close_i = close_arr[-i-2] if i < len(close_arr)-1 else close_arr[-1]
            open_i = open_arr[-i-1]
            high_i = high_arr[-i-1]
            low_i = low_arr[-i-1]
            close_i = close_arr[-i-1]
            vol_i = volume_arr[-i-1]
            涨幅_i = (close_i - prev_close_i) / prev_close_i * 100 if prev_close_i != 0 else 0
            
            # 计算波动率: MA(TR,30)/REF(C,1)*100
            
            # 计算波动率: MA(TR,30)/REF(C,1)*100
            涨幅_i = (close_i - prev_close_i) / prev_close_i * 100 if prev_close_i != 0 else 0
            涨幅_i = (close_i - prev_close_i) / prev_close_i * 100 if prev_close_i != 0 else 0
            
            # 计算波动率: MA(TR,30)/REF(C,1)*100
            if i < len(high_arr) - 1 and i < len(low_arr) - 1:
                tr_i = max(
                    high_i - low_i,
                    abs(high_i - close_arr[-i-2]) if i > 0 else 0,
                    abs(low_i - close_arr[-i-2]) if i > 0 else 0
                )
                波幅_i = np.mean([max(
                    high_arr[-(j+1)] - low_arr[-(j+1)],
                    abs(high_arr[-(j+1)] - close_arr[-(j+2)]) if j < len(close_arr)-1 else 0,
                    abs(low_arr[-(j+1)] - close_arr[-(j+2)]) if j < len(close_arr)-1 else 0
                ) for j in range(min(30, len(high_arr)-1))])
                波动率_i = 波幅_i / prev_close_i * 100 if prev_close_i != 0 else 0
            else:
                波动率_i = 0
            
            # 大长阳: C>O AND 涨跌幅>波动率*1.5 AND 涨跌幅>2
            大长阳_i = (close_i > open_i) and (涨幅_i > 波动率_i * 1.5) and (涨幅_i > 2)

            # 关键K
            vol_ma40 = np.mean(volume_arr[-40:]) if len(volume_arr) >= 40 else np.mean(volume_arr)
            关键K_i = (close_i > prev_close_i) and (vol_i > volume_arr[-i-2] * 1.8 if i > 0 else False) and 大长阳_i and (vol_i > vol_ma40)
            关键K_i = (close_i > prev_close_i) and (vol_i > volume_arr[-i-2] * 1.8 if i > 0 else False) and 大长阳_i and (vol_i > vol_ma40)
            
            # 暴力K
            ref_vol_i = volume_arr[-i-2] if i > 0 else volume_arr[-1]
            vol_ma60_i = np.mean(volume_arr[-60:]) if len(volume_arr) >= 60 else np.mean(volume_arr)
            K线长度_i = high_i - low_i
            上影线_i = high_i - max(close_i, open_i)
            
            cond1 = close_i > prev_close_i
            cond2 = vol_i > ref_vol_i * 1.8
            cond3 = 涨幅_i > 4
            cond4 = 上影线_i <= K线长度_i / 4
            cond5 = vol_i > vol_ma60_i
            
            暴力K_i = cond1 and cond2 and cond3 and cond4 and cond5
            
            if 关键K_i or 暴力K_i:
                has_keyK_or_blk = True
                break
    
    if not has_keyK_or_blk:
        return False
    
    # 6. 异动80: EXIST(VOL>MA(VOL,60)*2 AND C>O, 80)
    has_yidong = False
    for i in range(80):
        if i < len(volume_arr) - 1:
            vol_i = volume_arr[-i-1]
            close_i = close_arr[-i-1]
            open_i = open_arr[-i-1]
            vol_ma60_i = np.mean(volume_arr[-60:]) if len(volume_arr) >= 60 else np.mean(volume_arr)
            
            if (vol_i > vol_ma60_i * 2) and (close_i > open_i):
                has_yidong = True
                break
    
    if not has_yidong:
        return False
    
    return True

def calculate_blk_signal(indicators):
    """
    计算SCB版暴力K信号
    """
    close = indicators['close']
    prev_close = indicators['prev_close']
    open_price = indicators['open']
    high = indicators['high']
    low = indicators['low']
    volume = indicators['volume']
    vol_ma60 = indicators['vol_ma60']
    close_arr = indicators['close_arr']
    open_arr = indicators['open_arr']
    volume_arr = indicators['volume_arr']

    # 参考成交量: IF(REF(VOL,1)<=VOL/8,REF(VOL,2),REF(VOL,1))
    # volume_arr[-1]=当天, volume_arr[-2]=昨天, volume_arr[-3]=前天
    if volume_arr[-2] <= volume / 8:
        reference_volume = volume_arr[-3] if len(volume_arr) >= 3 else volume_arr[-2]
    else:
        reference_volume = volume_arr[-2]

    涨幅 = (close - prev_close) / prev_close * 100 if prev_close != 0 else 0
    K线长度 = high - low
    上影线 = high - max(close, open_price)
    
    cond1 = close > prev_close
    cond2 = volume > reference_volume * 1.8
    cond3 = 涨幅 > 4
    cond4 = 上影线 <= K线长度 / 3.5
    
    # 前15日涨幅 (REF(C,1) - REF(O,15)) / REF(O,15)
    cond5 = True
    if len(close_arr) >= 16 and len(open_arr) >= 16:
        open_15 = open_arr[-15]  # 15天前的开盘价
        if open_15 != 0:
            前15日涨幅 = (prev_close - open_15) / open_15 * 100
            cond5 = 前15日涨幅 < 4
    
    # 前9日涨幅 (REF(C,1) - REF(O,9)) / REF(O,9)
    cond6 = True
    if len(close_arr) >= 10 and len(open_arr) >= 10:
        open_9 = open_arr[-9]  # 9天前的开盘价
        if open_9 != 0:
            前9日涨幅 = (prev_close - open_9) / open_9 * 100
            cond6 = 前9日涨幅 < 4
    
    # 前4日涨幅 (REF(C,1) - REF(O,4)) / REF(O,4)
    cond7 = True
    if len(close_arr) >= 5 and len(open_arr) >= 5:
        open_4 = open_arr[-4]  # 4天前的开盘价
        if open_4 != 0:
            前4日涨幅 = (prev_close - open_4) / open_4 * 100
            cond7 = 前4日涨幅 < 4
    cond5 = True
    if len(close_arr) >= 16 and len(open_arr) >= 16:
        open_15 = open_arr[-16]  # 15天前的开盘价
        if open_15 != 0:
            前15日涨幅 = (prev_close - open_15) / open_15 * 100
            cond5 = 前15日涨幅 < 4
    
    # 前9日涨幅 (REF(C,1) - REF(O,9)) / REF(O,9)
    cond6 = True
    if len(close_arr) >= 10 and len(open_arr) >= 10:
        open_9 = open_arr[-10]  # 9天前的开盘价
        if open_9 != 0:
            前9日涨幅 = (prev_close - open_9) / open_9 * 100
            cond6 = 前9日涨幅 < 4
    
    # 前4日涨幅 (REF(C,1) - REF(O,4)) / REF(O,4)
    cond7 = True
    if len(close_arr) >= 5 and len(open_arr) >= 5:
        open_4 = open_arr[-5]  # 4天前的开盘价
        if open_4 != 0:
            前4日涨幅 = (prev_close - open_4) / open_4 * 100
            cond7 = 前4日涨幅 < 4

    
    cond8 = volume > vol_ma60
    
    blk_signal = cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7 and cond8
    
    return blk_signal

def calculate_scb_signal(indicators,blk_signal, dl_basic_history):
    """
    计算SCB综合信号（完全还原通达信公式）
    
    选股1 = REF(地量基础条件, 1)
    选股2 = REF(地量基础条件, 2)
    选股3 = REF(地量基础条件, 3)
    选股4 = REF(地量基础条件, 4)
    选股5 = REF(地量基础条件, 5)
    
    选股 = (选股1 OR 选股2 OR 选股3 OR 选股4 OR 选股5) AND 暴力K AND 知行多空线 > REF(知行多空线,60)
    """
    知行多空线 = indicators['知行多空线']
    知行多空线_arr = calculate_知行多空线_arr(indicators['close_arr'])
    知行多空线_60日前 = None
    if len(知行多空线_arr) >= 61:
        知行多空线_60日前 = 知行多空线_arr[-61]

    # 检查过去5天内是否满足地量基础条件
    has_dl_basic = False
    for offset in range(1, 6):  # 1-5天前
        idx = len(dl_basic_history) - offset
        if idx >= 0 and dl_basic_history[idx]:
            has_dl_basic = True
            break
    
    # 多头发散
    多头信号 = 知行多空线 > 知行多空线_60日前 if 知行多空线_60日前 else False
    
    # SCB综合信号
    scb_signal = has_dl_basic and blk_signal and 多头信号
    
    # 评分
    if scb_signal:
        scb_score = 10
    elif has_dl_basic and blk_signal:
        scb_score = 7
    elif has_dl_basic and 多头信号:
        scb_score = 4
    elif blk_signal and 多头信号:
        scb_score = 5
    elif has_dl_basic:
        scb_score = 2
    elif blk_signal:
        scb_score = 3
    else:
        scb_score = 0
    
    logger.info(f"\n=== SCB买入信号详情 ===")
    logger.info(f"过去5天满足地量基础条件: {has_dl_basic}")
    logger.info(f"今日暴力K: {blk_signal}")
    logger.info(f"多头发散: {多头信号}")
    logger.info(f"SCB信号: {scb_signal}")
    logger.info(f"SCB评分: {scb_score}")
    
    return scb_signal, scb_score
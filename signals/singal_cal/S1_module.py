import os
import logging
from datetime import datetime
import numpy as np
from typing import Dict

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

def calculate_s1_score(indicators: Dict) -> float:
    """计算S1卖出分数"""
    close = indicators['close']
    open_price = indicators['open']
    high = indicators['high']
    volume = indicators['volume']

    close_arr = indicators['close_arr']
    open_arr = indicators['open_arr']
    high_arr = indicators['high_arr']
    volume_arr = indicators['volume_arr']

    j = indicators['j']
    k = indicators['k']
    d = indicators['d']
    
    n = len(close_arr)
    
    if n < 60:
        return 0.0
    
    prev_close = close_arr[-2] if n >= 2 else close
    
    # 条件1基础
    前10日涨幅 = (close / close_arr[-10] - 1) * 100 if n >= 10 else 0
    前50日涨幅 = (close / close_arr[-50] - 1) * 100 if n >= 50 else 0
    
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
    
    # 条件2基础
    hhv_h_4 = np.max(high_arr[-4:])
    hhv_h_60 = np.max(high_arr[-60:])
    条件2基础 = (hhv_h_4 == hhv_h_60 and high != hhv_h_60)
    
    条件2评分 = 0
    if 条件2基础:
        涨幅 = (close - prev_close) / prev_close * 100 if prev_close != 0 else 0
        vol_ma5 = np.mean(volume_arr[-5:]) if n >= 5 else volume
        vol_ma10 = np.mean(volume_arr[-10:]) if n >= 10 else volume
        
        if (volume > vol_ma5 or volume > vol_ma10) and 涨幅 < -0.03 and close < open_price:
            ref_vol = volume_arr[-3] if n >= 3 else volume_arr[-1]
            if volume >= ref_vol * 1.2:
                条件2评分 = 12
    
    # 加分项
    加分1 = 0
    if 条件1基础:
        加分1 = 1.5
    
    加分2 = 0
    if j < k and k < d:
        加分2 = 0.8
    
    s1_score = 条件1评分 + 条件2评分 + 加分1 + 加分2

    logger.info("=== S1各条件得分详情 ===")
    logger.info(f"股票代码code: {indicators['code']}")
    logger.info(f"条件1得分: {条件1评分}")
    logger.info(f"条件2得分: {条件2评分}")
    logger.info(f"加分1: {加分1}")
    logger.info(f"加分2: {加分2}")      
    logger.info(f"\n>>> S1总分: {s1_score}")
    
    return s1_score
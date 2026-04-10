#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化信号系统 - scan_signals.py
全量计算每日市场信号

功能:
1. 获取全市场股票列表
2. 多进程并行计算每只股票的技术指标
3. 运行7个策略买入判断 + 卖出判断
4. 批量写入 daily_signals 表

用法:
    python scripts/scan_signals.py                    # 运行今日信号计算
    python scripts/scan_signals.py --date 20260311    # 运行指定日期
    python scripts/scan_signals.py --workers 10       # 指定进程数
"""

import os
import sys

from requests import get
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'singal_cal'))

import json
import logging
import argparse
from datetime import datetime
from typing import Optional, Dict, Any, List
from multiprocessing import Pool
from functools import partial

from backtrader import indicator
import numpy as np
import pandas as pd
import duckdb
from sqlalchemy import false

from basic_module import calculate_indicators

from S1_module import calculate_s1_score

from B1_strategy_module import calculate_b1_score
from B2_strategy_module import calculate_b2_score
from BLKB2_strategy_module import check_暴力K,check_倍量柱,check_J拐头向上
from SCB_strategy_module import calculate_dl_score,check_dl_basic_condition,calculate_blk_signal,calculate_scb_signal
from DZ30_strategy_module import calculate_倍量柱_arr,check_前20日非阴,check_长短期KD


def code_to_ts_code(code: str) -> str:
    """转换股票代码为tushare格式"""
    code = str(code)
    if code.startswith('6'):
        return f"{code}.SH"
    else:
        return f"{code}.SZ"


# 配置路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'Astock3.duckdb')

from scripts.log_utils import setup_logger
logger = setup_logger('scan_signals', 'pipeline')

# 让其他模块的日志也传播到 root logger
for module_name in ['basic_module', 'B1_strategy_module', 'B2_strategy_module', 'S1_module','BLKB2_strategy_module','SCB_strategy_module','DZ30_strategy_module']:
    module_logger = logging.getLogger(module_name)
    module_logger.propagate = True
    # 清除可能存在的所有 handler，避免重复
    for handler in module_logger.handlers[:]:
        module_logger.removeHandler(handler)

DEFAULT_WORKERS = 10  # 默认进程数
DATA_DAYS = 150  # 数据天数

def convert_to_serializable(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    else:
        return obj

def get_db_connection():
    """获取数据库连接"""
    return duckdb.connect(DB_PATH, read_only=True)  # 只读模式


def get_trading_date(date: Optional[str] = None) -> str:
    """获取交易日期"""
    latest = None
    if date:
        return f"{date[:4]}-{date[4:6]}-{date[6:]}"
    
    conn = get_db_connection()
    try:
        latest = conn.execute("SELECT MAX(trade_date) FROM dwd_daily_price").fetchone()[0]
        if latest:
            return str(latest)
    finally:
        conn.close()
    
    return latest if latest else datetime.now().strftime('%Y-%m-%d')


def get_stock_list() -> List[Dict]:
    """获取全市场股票列表"""
    conn = get_db_connection()
    try:
        df = conn.execute("""
            SELECT symbol AS code, name
            FROM dwd_stock_info
            WHERE list_status = 'L'
            ORDER BY symbol
        """).fetchdf()
        
        return df.to_dict('records')
    finally:
        conn.close()


def get_stock_data(code: str, trading_date: str, days: int = DATA_DAYS) -> Optional[pd.DataFrame]:
    """获取股票历史数据"""
    conn = get_db_connection()
    try:
        # 转换 code 格式为 ts_code 格式
        ts_code = code_to_ts_code(code)
        
        df = conn.execute("""
            SELECT ts_code, trade_date, open, high, low, close, vol
            FROM dwd_daily_price
            WHERE ts_code = ?
            AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        """, [ts_code, trading_date, days]).fetchdf()
        
        if df is not None and len(df) > 0:
            df = df.rename(columns={
                'ts_code': 'code',
                'trade_date': 'date',
                'vol': 'volume'
            })
        
        if df is None or len(df) < 60:
            return None
        
        df = df.sort_values('date').reset_index(drop=True)
        return df
    except Exception as e:
        logger.error(f"获取股票数据失败 {code}: {e}")
        return None
    finally:
        conn.close()

def get_positions(code: str) -> Optional[pd.DataFrame]:
    """获取持仓持仓信息"""
    conn = get_db_connection()
    try:
        df = conn.execute("""
            SELECT code, strategy, buy_price, status, buy_date
            FROM positions
            WHERE code = ?
            AND status = 'holding'
            ORDER BY buy_date DESC
        """, [code]).fetchdf()
        
        if df is None or len(df) < 1:
            return None
            
        df = df.sort_values('buy_date').reset_index(drop=True)
        return df
    finally:
        conn.close()

def get_positions_observation_state(code: str) -> Optional[bool]:
    """获取持仓股票的观察状态（从 positions 表读取）
    Returns:
        True: 处于观察期（前日跌破但未连续）
        False: 观察期已结束或无需观察
        None: 不在持仓中
    """
    conn = get_db_connection()
    try:
        df = conn.execute("""
            SELECT current_跌破多空线
            FROM positions
            WHERE code = ? AND status = 'holding'
        """, [code]).fetchdf()
        
        if df is None or len(df) < 1:
            return None
        
        val = df['current_跌破多空线'].values[0]
        # 处理 NULL 值
        if val is None:
            return False
        return bool(val)
    finally:
        conn.close()

def get_all_positions_observation_states() -> Dict[str, bool]:
    """获取所有持仓股票的观察状态（主进程调用，避免多进程锁冲突）
    
    Returns:
        Dict: {code: is_observing} - 持仓股票的观察状态字典
    """
    conn = get_db_connection()
    try:
        df = conn.execute("""
            SELECT code, current_跌破多空线
            FROM positions
            WHERE status = 'holding'
        """).fetchdf()
        
        if df is None or len(df) == 0:
            return {}
        
        # 转换：None/NA -> False
        result = {}
        for _, row in df.iterrows():
            val = row['current_跌破多空线']
            if val is None or pd.isna(val):
                result[row['code']] = False
            else:
                result[row['code']] = bool(val)
        return result
    finally:
        conn.close()

def update_all_positions_observation_states(updates: List[tuple]):
    """批量更新持仓股票的观察状态（主进程调用，避免多进程锁冲突）
    
    Args:
        updates: List[(code, is_observing), ...] - 需要更新的持仓状态
    """
    if not updates:
        return
    
    conn = duckdb.connect(DB_PATH, read_only=False)
    try:
        for code, is_observing in updates:
            conn.execute("""
                UPDATE positions
                SET current_跌破多空线 = ?
                WHERE code = ? AND status = 'holding'
            """, [is_observing, code])
        logger.info(f"批量更新 {len(updates)} 只持仓股票的观察状态")
    finally:
        conn.close()

def update_positions_observation_state(code: str, is_observing: bool):
    """更新持仓股票的观察状态到 positions 表"""
    conn = duckdb.connect(DB_PATH, read_only=False)
    try:
        conn.execute("""
            UPDATE positions
            SET current_跌破多空线 = ?
            WHERE code = ? AND status = 'holding'
        """, [is_observing, code])
    finally:
        conn.close()

# ==================== 买入信号计算模块 ====================
def get_b1_buy_signal(name: str, indicators: Dict, b1_threshold=8):
    try:
        KDJ_J低 = indicators['j'] < 13
        MACD_多头 = indicators['dif'] >= 0
        趋势线条件 = indicators['知行短期趋势线'] > indicators['知行多空线']
    
        b1_score = calculate_b1_score(indicators)
        
        # 保存当前B1分数和相关值
        B1总分 = b1_score
        buy_condition = (KDJ_J低 and MACD_多头 and 趋势线条件 and B1总分 >= b1_threshold)

        if buy_condition:
            logger.info(f"\n=== B1买入信号详情 ===")
            logger.info(datetime.now().strftime('%Y-%m-%d'))
            logger.info(f"股票代码code: {indicators['code']}")
            logger.info(f"B1总分: {B1总分}")
            logger.info(f"KDJ_J低于13: {KDJ_J低}")
            logger.info(f"J值: {indicators['j']}")
            logger.info(f"MACD_多头: {MACD_多头}")
            logger.info(f"短期趋势线>多空线: {趋势线条件}")

        return b1_score, buy_condition
    except Exception as e:
        logger.error(f"{indicators['code']} B1买入条件处理失败: {e}")
        logger.error(f"{name} B1买入条件处理失败: {e}")
    return 0, False

def get_b2_buy_signal(name: str, indicators: Dict, b2_threshold=8):
    try:
        # B2条件判断
        MACD_多头 = indicators['dif'] >= 0
        趋势线条件 = indicators['知行短期趋势线'] > indicators['知行多空线']
    
        b2_score = calculate_b2_score(indicators)

        logger.info(f"开始处理B2策略 {indicators['code']}")
        # 保存当前B2分数和相关值
        B2总分 = b2_score
        buy_condition = (MACD_多头 and 趋势线条件 and B2总分 >= b2_threshold)

        if buy_condition:
            logger.info(f"\n=== B2买入信号详情 ===")
            logger.info(datetime.now().strftime('%Y-%m-%d'))
            logger.info(f"股票代码code: {indicators['code']}")
            logger.info(f"B2总分: {B2总分}")
            logger.info(f"MACD_多头: {MACD_多头}")
            logger.info(f"短期趋势线>多空线: {趋势线条件}")

        return b2_score, buy_condition
    except Exception as e:
        logger.error(f"{indicators['code']} B2买入条件处理失败: {e}")
        logger.error(f"{name} B2买入条件处理失败: {e}")
    return 0, False

def get_BLK_buy_signal(name: str, indicators: Dict):
    try:
        score_blk =0
        趋势线条件 = indicators['知行短期趋势线'] > indicators['知行多空线']
        # 检查暴力K
        暴力K = check_暴力K(indicators)
        
        # 新策略买入条件: 非ST股 AND MACD_多头 AND 知行短期趋势线 > 知行多空线 
        # AND B2总分>=阈值 AND 暴力K AND 倍量柱 
        buy_condition = (趋势线条件 and 暴力K)

        if buy_condition:
            score_blk =7
            logger.info(f"\n=== 暴力k买入信号详情 ===")
            logger.info(datetime.now().strftime('%Y-%m-%d'))
            logger.info(f"股票代码code: {indicators['code']}")
            logger.info(f"短期趋势线>多空线: {趋势线条件}")
            logger.info(f"暴力K: {暴力K}")

        return score_blk, buy_condition
    except Exception as e:
        logger.error(f"{indicators['code']} 暴力k买入条件处理失败: {e}")
        logger.error(f"{name} 暴力k买入条件处理失败: {e}")
    return 0, False

def get_BLKB2_buy_signal(name: str, indicators: Dict, b2_threshold=8, score_b2=-999):
    try:
        score_blkB2 = 0
        # B2条件判断
        MACD_多头 = indicators['dif'] >= 0
        趋势线条件 = indicators['知行短期趋势线'] > indicators['知行多空线']
        
        # 计算B2得分
        b2_score = score_b2
        
        # 检查暴力K
        暴力K = check_暴力K(indicators)
        if 暴力K:
            score_blk =7
        
        # 检查倍量柱
        倍量柱 = check_倍量柱(indicators)
        if 倍量柱:
            score_blz =10
        
        # 检查J拐头向上
        J拐头向上 = check_J拐头向上(indicators)
        if J拐头向上:
            score_jt =10
        
        # 新策略买入条件: 非ST股 AND MACD_多头 AND 知行短期趋势线 > 知行多空线 
        # AND B2总分>=阈值 AND 暴力K AND 倍量柱 AND J拐头向上
        buy_condition = (MACD_多头 and 趋势线条件 and b2_score >= b2_threshold and 暴力K and 倍量柱 and J拐头向上)

        if buy_condition:
            score_blkB2 = score_blk*0.5 + b2_score*0.6+score_blz*0.2+score_jt*0.1
            logger.info(f"\n=== 暴力k+B2买入信号详情 ===")
            logger.info(datetime.now().strftime('%Y-%m-%d'))
            logger.info(f"股票代码code: {indicators['code']}")
            logger.info(f"B2总分: {b2_score}")
            logger.info(f"MACD_多头: {MACD_多头}")
            logger.info(f"短期趋势线>多空线: {趋势线条件}")
            logger.info(f"暴力K: {暴力K}")
            logger.info(f"倍量柱: {倍量柱}")
            logger.info(f"J拐头向上: {J拐头向上}")

        return score_blkB2, buy_condition
    except Exception as e:
        logger.error(f"{indicators['code']} 暴力k+B2买入条件处理失败: {e}")
        logger.error(f"{name} 暴力k+B2买入条件处理失败: {e}")
    return (0, False)

def get_SCB_buy_signal(name: str, indicators: Dict):
    try:
        dl_basic_history = []
        # 1. 检查地量基础条件，计算前5天的所有地量基础条件
        # 假设在扫描信号的循环中，对每一天都要计算
        for offset in range(1, 6):  # T-1, T-2, T-3, T-4, T-5
            # 构造 T-offset 那天所需的 indicators
            historical_indicators = {
                'code': indicators['code'],
                'close': indicators['close_arr'][-offset-1],
                'prev_close': indicators['close_arr'][-offset-2],
                'open': indicators['open_arr'][-offset-1],
                'high': indicators['high_arr'][-offset-1],
                'low': indicators['low_arr'][-offset-1],
                'volume': indicators['volume_arr'][-offset-1],
                'close_arr': indicators['close_arr'][:-(offset+1)],      # 截取到T-offset为止
                'open_arr': indicators['open_arr'][:-(offset+1)],
                'high_arr': indicators['high_arr'][:-(offset+1)],
                'low_arr': indicators['low_arr'][:-(offset+1)],
                'volume_arr': indicators['volume_arr'][:-(offset+1)],
            }
            
            # 检查那天是否满足地量基础条件
            dl_result = check_dl_basic_condition(historical_indicators)
            dl_basic_history.append(dl_result)
        
        # 2. 计算暴力K信号
        blk_signal = calculate_blk_signal(indicators)
        
        # 3. 计算SCB综合信号
        scb_signal, scb_score = calculate_scb_signal(indicators,blk_signal,dl_basic_history)
        
        # SCB买入条件: 地量 AND 暴力K AND 地量基础条件
        buy_condition = scb_signal

        if buy_condition:
            logger.info(f"\n=== 沙尘暴买入信号详情 ===")
            logger.info(datetime.now().strftime('%Y-%m-%d'))
            logger.info(f"股票代码code: {indicators['code']}")
            logger.info(f"地量基础条件: {dl_basic_history}")
            logger.info(f"暴力K: {blk_signal}")
            logger.info(f"SCB评分: {scb_score}")

        return scb_score, buy_condition
    except Exception as e:
        logger.error(f"{indicators['code']} 沙尘暴买入条件处理失败: {e}")
        logger.error(f"{name} 沙尘暴买入条件处理失败: {e}")
    return 0, False

def get_DZ30_buy_signal(name: str, indicators: Dict):
    try:
        score_dz30 = 0
        # 2. 今日条件: 长期>=85 AND 短期<=30
        短期KD,长期KD = check_长短期KD(indicators)
        今日条件 = (长期KD >= 80) and (短期KD <= 30)
        
        # 3. 价格在趋势线上
        价格在趋势线上 = indicators['close'] > indicators['知行短期趋势线']
        # 4. 趋势多头
        趋势多头 = indicators['知行短期趋势线'] > indicators['知行多空线']
        
        # 5. 倍量柱
        倍量柱_arr = calculate_倍量柱_arr(indicators)
        倍量柱_count = np.sum(倍量柱_arr[-20:]) if len(倍量柱_arr) >= 20 else np.sum(倍量柱_arr)
        有倍量柱 = 倍量柱_count >= 1
        
        # 6. 前20日非阴
        前20日非阴 = check_前20日非阴(indicators)
        
        # DZ30买入条件
        buy_condition = (今日条件  and 价格在趋势线上 and 
                       趋势多头 and 有倍量柱 and 前20日非阴)

        if buy_condition:
            score_dz30 = 5
            logger.info(f"\n=== 单针30买入信号详情 ===")
            logger.info(datetime.now().strftime('%Y-%m-%d'))
            logger.info(f"股票代码code: {indicators['code']}")
            logger.info(f"长期>85,短期<=30: {今日条件}")
            logger.info(f"价格在趋势线上: {价格在趋势线上}")
            logger.info(f"短期趋势线>多空线: {趋势多头}")
            logger.info(f"有倍量柱: {有倍量柱}")
            logger.info(f"前20日非阴: {前20日非阴}")

        return score_dz30, buy_condition
    except Exception as e:
        logger.error(f"{indicators['code']} 单针30买入条件处理失败: {e}")
        logger.error(f"{name} 单针30买入条件处理失败: {e}")
    return 0, False

# ==================== 卖出信号计算模块 ====================
def common_sell_signal(name: str, indicators: Dict, was_observing: bool = False):
    """
    Args:
        was_observing: 昨日是否处于观察期（从 positions 表读取）
    """
    score_s1 = calculate_s1_score(indicators)

    signal_s1_full = False
    signal_s1_half = False
    signal_跌破多空线 = False
    signal_止损 = False
    is_observing = False  # 当前观察状态输出

    # S1分数信号
    if score_s1 >= 5 and score_s1 < 10:
        signal_s1_half = True
    if score_s1 >= 10:
        signal_s1_full = True

    # 跌破多空线信号（带观察期缓冲）
    current_close = indicators['close']
    current_line = indicators['知行多空线']
    prev_close = indicators['close_arr'][-2]

    if current_close < current_line:
        if prev_close >= current_line:
            # 首次跌破：进入观察期
            is_observing = True
        elif was_observing:
            # 连续跌破：执行卖出
            signal_跌破多空线 = True
            is_observing = False  # 观察结束
    else:
        # 回到多空线之上：取消观察
        is_observing = False

    return score_s1, signal_s1_half, signal_s1_full, signal_跌破多空线, signal_止损, is_observing

def get_b1_sell_signal(name: str, indicators: Dict, positions_data: tuple = None, was_observing: bool = False):
    score_s1, signal_s1_half, signal_s1_full, signal_跌破多空线, signal_止损, _ = common_sell_signal(name, indicators, was_observing)
    
    if positions_data is not None:
        buy_price, _ = positions_data
        if buy_price and buy_price > 0:
            buy_price_cost = buy_price * 1.0005  # 含买入手续费
            intraday_low = indicators['low']
            profit_pct_low = (intraday_low - buy_price_cost) / buy_price_cost * 100
            if profit_pct_low < -3:
                signal_止损 = True
    
    sell_condition = (signal_s1_full or signal_s1_half or signal_跌破多空线 or signal_止损)

    if sell_condition:
        logger.info(f"\n=== B1卖出信号详情 ===")
        logger.info(datetime.now().strftime('%Y-%m-%d'))
        logger.info(f"股票代码code: {indicators['code']}")
        logger.info(f"股票名称: {name}")
        logger.info(f"S1分数: {score_s1}")
        logger.info(f"S1分数>=10清仓: {signal_s1_full}")
        logger.info(f"S1分数>=5清半仓: {signal_s1_half}")
        logger.info(f"跌破多空线: {signal_跌破多空线}")
        logger.info(f"3%止损: {signal_止损}")
        logger.info(f"当天收盘价: {indicators['close']}")
        logger.info(f"当天的多空线: {indicators['知行多空线']}")

    return sell_condition

def get_b2_sell_signal(name: str, indicators: Dict, positions_data: tuple = None, was_observing: bool = False):
    score_s1, signal_s1_half, signal_s1_full, signal_跌破多空线, signal_止损, _ = common_sell_signal(name, indicators, was_observing)
    
    if positions_data is not None:
        buy_price, _ = positions_data
        if buy_price and buy_price > 0:
            buy_price_cost = buy_price * 1.0005  # 含买入手续费
            intraday_low = indicators['low']
            profit_pct_low = (intraday_low - buy_price_cost) / buy_price_cost * 100
            if profit_pct_low < -3:
                signal_止损 = True
    
    sell_condition = (signal_s1_full or signal_s1_half or signal_跌破多空线 or signal_止损)

    if sell_condition:
        logger.info(f"\n=== B2卖出信号详情 ===")
        logger.info(datetime.now().strftime('%Y-%m-%d'))
        logger.info(f"股票代码code: {indicators['code']}")
        logger.info(f"股票名称: {name}")
        logger.info(f"S1分数: {score_s1}")
        logger.info(f"S1分数>=10清仓: {signal_s1_full}")
        logger.info(f"S1分数>=5清半仓: {signal_s1_half}")
        logger.info(f"跌破多空线: {signal_跌破多空线}")
        logger.info(f"3%止损: {signal_止损}")
        logger.info(f"当天收盘价: {indicators['close']}")
        logger.info(f"当天的多空线: {indicators['知行多空线']}")

    return sell_condition

def get_BLKB2_sell_signal(name: str, indicators: Dict, positions_data: tuple = None, was_observing: bool = False):
    score_s1, signal_s1_half, signal_s1_full, signal_跌破多空线, signal_止损, _ = common_sell_signal(name, indicators, was_observing)
    
    if positions_data is not None:
        buy_price, _ = positions_data
        if buy_price and buy_price > 0:
            buy_price_cost = buy_price * 1.0005  # 含买入手续费
            intraday_low = indicators['low']
            profit_pct_low = (intraday_low - buy_price_cost) / buy_price_cost * 100
            if profit_pct_low < -3:
                signal_止损 = True
    
    sell_condition = (signal_s1_full or signal_s1_half or signal_跌破多空线 or signal_止损)

    if sell_condition:
        logger.info(f"\n=== 暴力k+B2卖出信号详情 ===")
        logger.info(datetime.now().strftime('%Y-%m-%d'))
        logger.info(f"股票代码code: {indicators['code']}")
        logger.info(f"股票名称: {name}")
        logger.info(f"S1分数: {score_s1}")
        logger.info(f"S1分数>=10清仓: {signal_s1_full}")
        logger.info(f"S1分数>=5清半仓: {signal_s1_half}")
        logger.info(f"跌破多空线: {signal_跌破多空线}")
        logger.info(f"3%止损: {signal_止损}")
        logger.info(f"当天收盘价: {indicators['close']}")
        logger.info(f"当天的多空线: {indicators['知行多空线']}")

    return sell_condition

def get_BLK_sell_signal(name: str, indicators: Dict, positions_data: tuple = None, was_observing: bool = False):
    score_s1, signal_s1_half, signal_s1_full, signal_跌破多空线, signal_止损, _ = common_sell_signal(name, indicators, was_observing)
    
    if positions_data is not None:
        buy_price, _ = positions_data
        if buy_price and buy_price > 0:
            buy_price_cost = buy_price * 1.0005  # 含买入手续费
            intraday_low = indicators['low']
            profit_pct_low = (intraday_low - buy_price_cost) / buy_price_cost * 100
            if profit_pct_low < -3:
                signal_止损 = True
    
    sell_condition = (signal_s1_full or signal_s1_half or signal_跌破多空线 or signal_止损)

    if sell_condition:
        logger.info(f"\n=== 暴力k卖出信号详情 ===")
        logger.info(datetime.now().strftime('%Y-%m-%d'))
        logger.info(f"股票代码code: {indicators['code']}")
        logger.info(f"股票名称: {name}")
        logger.info(f"S1分数: {score_s1}")
        logger.info(f"S1分数>=10清仓: {signal_s1_full}")
        logger.info(f"S1分数>=5清半仓: {signal_s1_half}")
        logger.info(f"跌破多空线: {signal_跌破多空线}")
        logger.info(f"3%止损: {signal_止损}")
        logger.info(f"当天收盘价: {indicators['close']}")
        logger.info(f"当天的多空线: {indicators['知行多空线']}")

    return sell_condition
    
def get_SCB_sell_signal(name: str, indicators: Dict, positions_data: tuple = None, was_observing: bool = False):
    score_s1, signal_s1_half, signal_s1_full, signal_跌破多空线, signal_止损, _ = common_sell_signal(name, indicators, was_observing)
    
    if positions_data is not None:
        buy_price, _ = positions_data
        if buy_price and buy_price > 0:
            buy_price_cost = buy_price * 1.0005  # 含买入手续费
            intraday_low = indicators['low']
            profit_pct_low = (intraday_low - buy_price_cost) / buy_price_cost * 100
            if profit_pct_low < -3:
                signal_止损 = True
    
    sell_condition = (signal_s1_full or signal_s1_half or signal_跌破多空线 or signal_止损)

    if sell_condition:
        logger.info(f"\n=== 沙尘暴卖出信号详情 ===")
        logger.info(datetime.now().strftime('%Y-%m-%d'))
        logger.info(f"股票代码code: {indicators['code']}")
        logger.info(f"股票名称: {name}")
        logger.info(f"S1分数: {score_s1}")
        logger.info(f"S1分数>=10清仓: {signal_s1_full}")
        logger.info(f"S1分数>=5清半仓: {signal_s1_half}")
        logger.info(f"跌破多空线: {signal_跌破多空线}")
        logger.info(f"3%止损: {signal_止损}")
        logger.info(f"当天收盘价: {indicators['close']}")
        logger.info(f"当天的多空线: {indicators['知行多空线']}")

    return sell_condition

def get_DZ30_sell_signal(name: str, indicators: Dict, positions_data: tuple = None, was_observing: bool = False):
    score_s1, signal_s1_half, signal_s1_full, signal_跌破多空线, signal_止损, _ = common_sell_signal(name, indicators, was_observing)
    
    if positions_data is not None:
        buy_price, _ = positions_data
        if buy_price and buy_price > 0:
            buy_price_cost = buy_price * 1.0005  # 含买入手续费
            intraday_low = indicators['low']
            profit_pct_low = (intraday_low - buy_price_cost) / buy_price_cost * 100
            if profit_pct_low < -3:
                signal_止损 = True
    
    sell_condition = (signal_s1_full or signal_s1_half or signal_跌破多空线 or signal_止损)

    if sell_condition:
        logger.info(f"\n=== 单针30卖出信号详情 ===")
        logger.info(datetime.now().strftime('%Y-%m-%d'))
        logger.info(f"股票代码code: {indicators['code']}")
        logger.info(f"股票名称: {name}")
        logger.info(f"S1分数: {score_s1}")
        logger.info(f"S1分数>=10清仓: {signal_s1_full}")
        logger.info(f"S1分数>=5清半仓: {signal_s1_half}")
        logger.info(f"跌破多空线: {signal_跌破多空线}")
        logger.info(f"3%止损: {signal_止损}")
        logger.info(f"当天收盘价: {indicators['close']}")
        logger.info(f"当天的多空线: {indicators['知行多空线']}")

    return sell_condition

# ==================== 股票处理模块 ====================
def process_single_stock(args: tuple) -> Optional[Dict]:
    """处理单只股票"""
    code, name, trading_date, was_observing = args

    df = get_stock_data(code, trading_date)

    if df is None or len(df) < 60:
        return None
    indicators = calculate_indicators(df)

    b1_threshold = 8
    b2_threshold = 8
    
    try:
        # 持仓数据
        positions = get_positions(code)
        positions_data = None
        if positions is not None and len(positions) > 0:
            buy_price = positions['buy_price'].values[0]
            strategy = positions['strategy'].values[0]
            positions_data = (buy_price, strategy)
        
        # 买入信号
        score_b1,b1_buy_condition = get_b1_buy_signal(name, indicators, b1_threshold)
        score_b2,b2_buy_condition = get_b2_buy_signal(name, indicators, b2_threshold)
        score_blkB2,BLKB2_buy_condition = get_BLKB2_buy_signal(name, indicators, b2_threshold, score_b2)
        score_blk, BLK_buy_condition = get_BLK_buy_signal(name, indicators)
        scb_score, SCB_buy_condition = get_SCB_buy_signal(name, indicators)
        score_dz30, DZ30_buy_condition = get_DZ30_buy_signal(name, indicators)
        
        # ── Step 2: 计算 S1 信号和观察状态 ──
        score_s1, signal_s1_half, signal_s1_full, signal_跌破多空线, signal_止损, current_observing = \
            common_sell_signal(name, indicators, was_observing)

        # ── 止损信号计算（使用缓存的 positions_data）──
        if positions_data is not None:
            buy_price, _ = positions_data
            if buy_price and buy_price > 0:
                buy_price_cost = buy_price * 1.0005  # 含买入手续费
                intraday_low = indicators['low']
                profit_pct_low = (intraday_low - buy_price_cost) / buy_price_cost * 100
                if profit_pct_low < -3:
                    signal_止损 = True

        b1_sell_condition = get_b1_sell_signal(name, indicators, positions_data, was_observing)
        b2_sell_condition = get_b2_sell_signal(name, indicators, positions_data, was_observing)
        BLKB2_sell_condition = get_BLKB2_sell_signal(name, indicators, positions_data, was_observing)
        BLK_sell_condition = get_BLK_sell_signal(name, indicators, positions_data, was_observing)
        SCB_sell_condition = get_SCB_sell_signal(name, indicators, positions_data, was_observing)
        DZ30_sell_condition = get_DZ30_sell_signal(name, indicators, positions_data, was_observing)
        
        
        # 转换numpy array为list以便JSON序列化
        # 结果记录
        indicators_serializable = convert_to_serializable(indicators)
        result = {
            'date': trading_date,
            'code': code,
            'name': name,
            
            'open': indicators['open'],
            'high': indicators['high'],
            'low': indicators['low'],
            'close': indicators['close'],
            'volume': indicators['volume'],
            'prev_close': indicators['prev_close'],
            'change_pct': indicators['涨幅'],

            'score_b1': score_b1,
            'score_b2': score_b2,
            'score_blk': score_blk,
            'score_dl': 0,
            'score_dz30': score_dz30,
            'score_scb': scb_score,
            'score_blkB2': score_blkB2,   
            
            'signal_buy_b1': b1_buy_condition,
            'signal_buy_b2': b2_buy_condition,
            'signal_buy_blk': BLK_buy_condition,    
            'signal_buy_dl': False,
            'signal_buy_dz30': DZ30_buy_condition,
            'signal_buy_scb': SCB_buy_condition,
            'signal_buy_blkB2': BLKB2_buy_condition,

            'signal_sell_b1': b1_sell_condition,
            'signal_sell_b2': b2_sell_condition,
            'signal_sell_blk': BLK_sell_condition,
            'signal_sell_dl': False,
            'signal_sell_dz30': DZ30_sell_condition,
            'signal_sell_scb': SCB_sell_condition,
            'signal_sell_blkB2': BLKB2_sell_condition,

            'score_s1': score_s1,
            'signal_s1_full': signal_s1_full,
            'signal_s1_half': signal_s1_half,
            'signal_跌破多空线': signal_跌破多空线,
            'signal_止损': signal_止损,
            'is_observing': current_observing,
            'indicators': json.dumps(indicators_serializable, ensure_ascii=False)
        }
        return result
    except Exception as e:
        logger.error(f"处理股票 {code} 失败: {e}")
        logger.error(f"处理股票 {name} 失败: {e}")
        return None


def scan_signals(trading_date: str, workers: int = DEFAULT_WORKERS) -> Dict[str, Any]:
    """扫描信号"""
    logger.info(f"开始扫描信号: {trading_date}, 进程数: {workers}")
    start_time = datetime.now()
    
    stocks = get_stock_list()
    logger.info(f"获取到 {len(stocks)} 只股票")
    
    # Pool前：读取所有持仓股观察状态快照
    positions_observing_snapshot = get_all_positions_observation_states()
    logger.info(f"获取 {len(positions_observing_snapshot)} 只持仓股的观察状态")
    
    args_list = [
        (s['code'], s['name'], trading_date, 
         positions_observing_snapshot.get(s['code'], False))
        for s in stocks
    ]
    
    results = []
    observation_updates = []
    success_count = 0
    fail_count = 0
    
    with Pool(processes=workers) as pool:
        for result in pool.imap_unordered(process_single_stock, args_list, chunksize=50):
            if result:
                results.append(result)
                success_count += 1
                # 收集持仓股的观察状态更新
                if result['code'] in positions_observing_snapshot:
                    observation_updates.append((result['code'], result.get('is_observing', False)))
            else:
                fail_count += 1
            
            total = success_count + fail_count
            if total % 500 == 0:
                logger.info(f"进度: {total}/{len(stocks)}")
    
    # Pool后：批量更新positions表
    if observation_updates:
        update_all_positions_observation_states(observation_updates)
    
    logger.info(f"处理完成: 成功 {success_count}, 失败 {fail_count}")
    
    if results:
        # 使用新的写连接（解决只读模式的锁问题）
        conn = duckdb.connect(DB_PATH, read_only=False)
        try:
            # 创建表（如果不存在）
            conn.execute("""
                CREATE TABLE if not exists daily_signals (
                    date DATE,
                    code VARCHAR,
                    name VARCHAR,
                    
                    -- OHLC数据
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume DOUBLE,
                    prev_close DOUBLE,
                    change_pct DOUBLE,
                    
                    -- 买入分数
                    score_b1 DOUBLE,
                    score_b2 DOUBLE,
                    score_blk DOUBLE,
                    score_dl DOUBLE,
                    score_dz30 DOUBLE,
                    score_scb DOUBLE,
                    score_blkB2 DOUBLE,
                    
                    -- 买入信号
                    signal_buy_b1 BOOLEAN,
                    signal_buy_b2 BOOLEAN,
                    signal_buy_blk BOOLEAN,
                    signal_buy_dl BOOLEAN,
                    signal_buy_dz30 BOOLEAN,
                    signal_buy_scb BOOLEAN,
                    signal_buy_blkB2 BOOLEAN,

                    -- 策略卖出信号
                    signal_sell_b1 BOOLEAN,
                    signal_sell_b2 BOOLEAN,
                    signal_sell_blk BOOLEAN,
                    signal_sell_dl BOOLEAN,
                    signal_sell_dz30 BOOLEAN,
                    signal_sell_scb BOOLEAN,
                    signal_sell_blkB2 BOOLEAN,
                    
                    -- 卖出分数
                    score_s1 DOUBLE,
                    
                    -- 分数卖出信号
                    signal_s1_full BOOLEAN,
                    signal_s1_half BOOLEAN,
                    signal_跌破多空线 BOOLEAN,
                    signal_止损 BOOLEAN,

                    is_observing BOOLEAN,
                    
                    -- 技术指标
                    indicators JSON,
                    
                    PRIMARY KEY (date, code)
                );
                """)
            conn.execute("DELETE FROM daily_signals WHERE date = ?", [trading_date])
            
            results_db = pd.DataFrame(results)
            conn.execute("INSERT INTO daily_signals BY NAME SELECT * FROM results_db")
            
            logger.info(f"写入数据库 {len(results)} 条记录")
        except Exception as e:
            logger.error(f"写入数据库失败: {e}")
            raise
        finally:
            conn.close()
    
    signal_stats = {
        'signal_buy_b1': sum(1 for r in results if r['signal_buy_b1']),
        'signal_buy_b2': sum(1 for r in results if r['signal_buy_b2']),
        'signal_buy_blk': sum(1 for r in results if r['signal_buy_blk']),
        'signal_buy_dl': sum(1 for r in results if r['signal_buy_dl']),
        'signal_buy_dz30': sum(1 for r in results if r['signal_buy_dz30']),
        'signal_buy_scb': sum(1 for r in results if r['signal_buy_scb']),
        'signal_buy_blkB2': sum(1 for r in results if r['signal_buy_blkB2']),

        'signal_sell_b1': sum(1 for r in results if r['signal_sell_b1']),
        'signal_sell_b2': sum(1 for r in results if r['signal_sell_b2']),
        'signal_sell_blk': sum(1 for r in results if r['signal_sell_blk']),
        'signal_sell_dl': sum(1 for r in results if r['signal_sell_dl']),
        'signal_sell_dz30': sum(1 for r in results if r['signal_sell_dz30']),
        'signal_sell_scb': sum(1 for r in results if r['signal_sell_scb']),
        'signal_sell_blkB2': sum(1 for r in results if r['signal_sell_blkB2']),

        'signal_跌破多空线': sum(1 for r in results if r['signal_跌破多空线']),
        'signal_止损': sum(1 for r in results if r['signal_止损']),
        'signal_s1_full': sum(1 for r in results if r['signal_s1_full']),
        'signal_s1_half': sum(1 for r in results if r['signal_s1_half']),
    }
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info(f"扫描完成，耗时: {duration:.1f}秒")
    logger.info(f"信号统计: {signal_stats}")
    
    # ===== 流水线日志记录 =====
    try:
        from scripts.pipeline_manager import write_step_log
        
        # 统计信号
        buy_signals = sum(1 for r in results if r and (r.get('signal_buy_b1') or r.get('signal_buy_b2')))
        sell_signals = sum(1 for r in results if r and (r.get('signal_sell_b1') or r.get('signal_sell_b2')))
        
        b1_signals = sum(1 for r in results if r and r.get('signal_buy_b1'))
        b2_signals = sum(1 for r in results if r and r.get('signal_buy_b2'))
        blk_signals = sum(1 for r in results if r and r.get('signal_buy_blk'))
        
        # 获取 pipeline_id
        pipeline_id = os.environ.get('PIPELINE_ID', f"manual_{datetime.now().strftime('%Y%m%d')}")
        
        write_step_log(pipeline_id, 'signals', {
            'update_type': 'daily',
            'start_time': start_time,
            'end_time': end_time,
            'duration_sec': duration,
            'expected_count': len(stocks),
            'actual_count': success_count,
            'is_success': True,
            'step_details': {
                'target_date': trading_date,
                'buy_signals_count': buy_signals,
                'sell_signals_count': sell_signals,
                'b1_signals': b1_signals,
                'b2_signals': b2_signals,
                'blk_signals': blk_signals,
            }
        })
    except Exception as e:
        logger.warning(f"写入流水线日志失败: {e}")
    # ===== 流水线日志记录结束 =====
    
    return {
        'date': trading_date,
        'total_stocks': len(stocks),
        'success_count': success_count,
        'fail_count': fail_count,
        'signal_stats': signal_stats,
        'duration': duration,
    }


def main():
    parser = argparse.ArgumentParser(description='量化信号扫描')
    parser.add_argument('--date', type=str, help='交易日期 YYYYMMDD')
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS, help=f'进程数 (默认{DEFAULT_WORKERS})')
    args = parser.parse_args()
    
    trading_date = get_trading_date(args.date)
    logger.info(f"trading_date: {trading_date}")

    trading_date_fmt = trading_date.replace('-', '')
    
    logger.info(f"=== 量化信号扫描启动 ===")
    logger.info(f"日期: {trading_date_fmt}")
    logger.info(f"进程数: {args.workers}")
    
    result = scan_signals(trading_date, args.workers)
    
    logger.info(f"=== 扫描完成 ===")
    logger.info(f"总股票: {result['total_stocks']}")
    logger.info(f"成功: {result['success_count']}")
    logger.info(f"失败: {result['fail_count']}")
    logger.info(f"信号: {result['signal_stats']}")
    logger.info(f"耗时: {result['duration']:.1f}秒")


if __name__ == '__main__':
    main()

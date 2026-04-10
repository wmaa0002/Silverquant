"""
策略基类框架

基于天宫B1/B2策略总结的通用策略框架
支持打分策略模式和信号策略模式

使用方式:
    class MyStrategy(BaseStrategy):
        params = (
            ('threshold', 8.0),
            ('stop_loss_pct', 0.05),
        )
        
        def calculate_score(self) -> float:
            # 实现打分逻辑
            return score
            
        def buy_condition(self) -> bool:
            # 实现买入条件
            return score >= self.params.threshold
            
        def sell_condition(self) -> bool:
            # 实现卖出条件
            return should_sell
"""
import backtrader as bt
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


class BaseStrategy(bt.Strategy):
    """
    策略基类
    
    子类需要实现以下方法:
    - calculate_score(): 计算策略分数
    - buy_condition(): 买入条件判断
    - sell_condition(): 卖出条件判断
    """
    
    params = (
        ('threshold', 8.0),       # 分数门槛
        ('stop_loss_pct', 0.05), # 止损比例
        ('min_data_points', 60),  # 最少数据点数
        ('debug_mode', False),    # 调试模式
    )
    
    # 节假日列表（与天宫B1/B2策略相同）
    节假日列表 = [
        datetime(2024, 2, 12), datetime(2024, 2, 13), datetime(2024, 2, 14),
        datetime(2024, 4, 4), datetime(2024, 4, 5), datetime(2024, 5, 1),
        datetime(2024, 5, 2), datetime(2024, 5, 3), datetime(2024, 6, 10),
        datetime(2024, 9, 16), datetime(2024, 9, 17), datetime(2024, 10, 1),
        datetime(2024, 10, 2), datetime(2024, 10, 3), datetime(2024, 10, 4),
        datetime(2024, 10, 7), datetime(2025, 1, 28), datetime(2025, 1, 29),
        datetime(2025, 1, 30), datetime(2025, 1, 31), datetime(2025, 4, 4),
        datetime(2025, 5, 1), datetime(2025, 5, 2), datetime(2025, 6, 2),
        datetime(2025, 10, 1), datetime(2025, 10, 2), datetime(2025, 10, 3),
        datetime(2025, 10, 6), datetime(2025, 10, 7), datetime(2025, 10, 8),
        datetime(2026, 1, 1), datetime(2026, 1, 2), datetime(2026, 1, 3),
        datetime(2026, 2, 15), datetime(2026, 2, 16), datetime(2026, 2, 17),
        datetime(2026, 2, 18), datetime(2026, 2, 19), datetime(2026, 2, 20),
        datetime(2026, 2, 21), datetime(2026, 2, 22), datetime(2026, 2, 23),
        datetime(2026, 4, 4), datetime(2026, 4, 5), datetime(2026, 4, 6),
        datetime(2026, 5, 1), datetime(2026, 5, 2), datetime(2026, 5, 3),
        datetime(2026, 5, 4), datetime(2026, 5, 5), datetime(2026, 6, 19),
        datetime(2026, 6, 20), datetime(2026, 6, 21), datetime(2026, 9, 25),
        datetime(2026, 9, 26), datetime(2026, 9, 27), datetime(2026, 10, 1),
        datetime(2026, 10, 2), datetime(2026, 10, 3), datetime(2026, 10, 4),
        datetime(2026, 10, 5), datetime(2026, 10, 6), datetime(2026, 10, 7)
    ]
    
    def __init__(self):
        self._init_data_aliases()
        self._init_tracking_vars()
        self._init_indicators()
        
    def _init_data_aliases(self):
        """初始化数据别名"""
        self.close = self.data.close
        self.open = self.data.open
        self.high = self.data.high
        self.low = self.data.low
        self.volume = self.data.volume
        
    def _init_tracking_vars(self):
        """初始化跟踪变量"""
        self.entry_price = None
        self.order = None
        
        self.pending_buy_signal = False
        self.pending_buy_reason = ""
        self.pending_buy_date = None
        
        self.pending_sell_signal = False
        self.pending_sell_reason = ""
        
        self.trade_records = []
        
        self.prev_k = None
        self.prev_d = None
        
    def _init_indicators(self):
        """初始化指标缓存，子类可重写"""
        pass
        
    # =========================================
    # 核心方法 - 子类必须实现
    # =========================================
    
    def calculate_score(self) -> float:
        """
        计算策略分数
        
        Returns:
            float: 策略分数
        """
        raise NotImplementedError("子类必须实现 calculate_score 方法")
        
    def buy_condition(self) -> bool:
        """
        买入条件
        
        Returns:
            bool: 是否触发买入
        """
        score = self.calculate_score()
        return score >= self.params.threshold
        
    def sell_condition(self) -> bool:
        """
        卖出条件
        
        Returns:
            bool: 是否触发卖出
        """
        return False
        
    # =========================================
    # 工具方法 - 子类可调用
    # =========================================
    
    def get_price_arrays(self) -> Dict[str, np.ndarray]:
        """获取价格数组"""
        return {
            'close': np.array(self.close.array[:len(self)]),
            'high': np.array(self.high.array[:len(self)]),
            'low': np.array(self.low.array[:len(self)]),
            'volume': np.array(self.volume.array[:len(self)]),
            'open': np.array(self.open.array[:len(self)]),
        }
    
    def get_current_price(self) -> Dict[str, float]:
        """获取当前价格"""
        return {
            'close': self.close[0],
            'open': self.open[0],
            'high': self.high[0],
            'low': self.low[0],
            'volume': self.volume[0],
        }
    
    def calculate_ma(self, period: int) -> float:
        """计算移动平均"""
        close_arr = np.array(self.close.array[:len(self)])
        if len(close_arr) < period:
            return close_arr[-1]
        return np.mean(close_arr[-period:])
    
    def calculate_ema(self, period: int) -> float:
        """计算EMA"""
        close_arr = np.array(self.close.array[:len(self)])
        if len(close_arr) < period:
            return close_arr[-1]
        
        ema = close_arr[-1]
        multiplier = 2 / (period + 1)
        
        for i in range(2, period + 1):
            if i <= len(close_arr):
                ema = ema * (1 - multiplier) + close_arr[-i] * multiplier
        
        return ema
    
    def calculate_dif(self) -> float:
        """计算DIF (MACD差值)"""
        ema12 = self.calculate_ema(12)
        ema26 = self.calculate_ema(26)
        return ema12 - ema26
    
    def calculate_rsi(self, period: int = 14) -> float:
        """计算RSI"""
        close_arr = np.array(self.close.array[:len(self)])
        
        if len(close_arr) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(1, period + 1):
            diff = close_arr[-i] - close_arr[-i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses) if np.mean(losses) != 0 else 0.001
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def calculate_kdj(self) -> tuple:
        """计算KDJ指标 (K, D, J)"""
        close_arr = np.array(self.close.array[:len(self)])
        low_arr = np.array(self.low.array[:len(self)])
        high_arr = np.array(self.high.array[:len(self)])
        
        n = 9
        if len(close_arr) < n:
            return 50.0, 50.0, 50.0
        
        lowest_low = np.min(low_arr[-n:])
        highest_high = np.max(high_arr[-n:])
        
        rsv = (close_arr[-1] - lowest_low) / (highest_high - lowest_low) * 100 if highest_high != lowest_low else 50
        
        k = 2/3 * (self.prev_k if self.prev_k else 50) + 1/3 * rsv
        d = 2/3 * (self.prev_d if self.prev_d else 50) + 1/3 * k
        j = 3 * k - 2 * d
        
        self.prev_k = k
        self.prev_d = d
        
        return k, d, j
    
    def calculate_bbi(self) -> float:
        """计算BBI指标"""
        ma3 = self.calculate_ma(3)
        ma6 = self.calculate_ma(6)
        ma12 = self.calculate_ma(12)
        ma24 = self.calculate_ma(24)
        return (ma3 + ma6 + ma12 + ma24) / 4
    
    def get_position_size(self, price: float) -> int:
        """计算买入数量"""
        cash = self.broker.getcash()
        available_cash = cash * 0.95
        size = int(available_cash / price / 100) * 100
        return max(size, 100)
    
    # =========================================
    # 时间过滤 - 子类可重写
    # =========================================
    
    def time_filter(self) -> bool:
        """时间过滤，返回False跳过当前bar"""
        if len(self) <= self.params.min_data_points:
            return False
        
        if self.order:
            return False
            
        return True
    
    def is_time_filtered(self, current_time=None) -> Tuple[bool, str]:
        """
        时间过滤检查
        
        检查当前时间是否在过滤时间段内（14:30尾盘、节假日、连续下跌等）
        
        Args:
            current_time: 可选的时间对象，默认使用当前bar的时间
            
        Returns:
            Tuple[bool, str]: (是否被过滤, 过滤原因)
        """
        if current_time is None:
            current_date = self.datas[0].datetime.datetime(0)
        else:
            current_date = current_time
        
        if current_date.hour == 14 and current_date.minute >= 30:
            return (True, "14:30尾盘过滤")
        
        for holiday in self.节假日列表:
            if current_date.date() == holiday.date():
                return (True, f"节假日过滤:{holiday.strftime('%Y-%m-%d')}")
        
        if len(self) >= 5:
            close_arr = np.array(self.close.array[:len(self)])
            recent_5 = close_arr[-5:]
            price_changes = []
            for i in range(1, len(recent_5)):
                pct_change = (recent_5[i] - recent_5[i-1]) / recent_5[i-1] * 100
                price_changes.append(pct_change)
            
            if len(price_changes) >= 3:
                consecutive_down = 0
                for pc in reversed(price_changes):
                    if pc < -3:
                        consecutive_down += 1
                    else:
                        break
                
                if consecutive_down >= 3:
                    return (True, "连续下跌过滤")
        
        return (False, "")
    
    # =========================================
    # 主循环 - 通常不需要修改
    # =========================================
    
    def next(self):
        """主循环，每根K线执行一次"""
        if not self.time_filter():
            return
        
        if not self.position:
            if self.buy_condition():
                self._execute_buy()
        else:
            if self.sell_condition():
                self._execute_sell()
    
    def _execute_buy(self):
        """执行买入"""
        price = self.close[0]
        size = self.get_position_size(price)
        
        if size < 100:
            return
        
        self.pending_buy_signal = True
        self.pending_buy_date = self.datas[0].datetime.datetime(0)
        self.pending_buy_reason = f"分数:{self.calculate_score():.1f}"
        
        self.order = self.buy(size=size)
    
    def _execute_sell(self):
        """执行卖出"""
        self.order = self.close()
    
    def notify_order(self, order):
        """订单通知处理"""
        if order.status in [order.Completed]:
            date = self.datas[0].datetime.datetime(0)
            
            if order.isbuy():
                self.entry_price = order.executed.price
                self.pending_buy_signal = False
                
                self._record_trade({
                    'date': date,
                    'action': 'BUY',
                    'price': order.executed.price,
                    'size': order.executed.size,
                    'reason': self.pending_buy_reason
                })
                
            elif order.issell():
                pnl = 0
                if self.entry_price:
                    pnl = (order.executed.price - self.entry_price) / self.entry_price * 100
                
                self._record_trade({
                    'date': date,
                    'action': 'SELL',
                    'price': order.executed.price,
                    'size': order.executed.size,
                    'pnl': pnl,
                    'reason': self.pending_sell_reason
                })
                
                self.entry_price = None
                
            self.order = None
    
    def _record_trade(self, trade_record: Dict):
        """记录交易"""
        self.trade_records.append(trade_record)
        
        if self.params.debug_mode:
            print(f"交易: {trade_record['date']} {trade_record['action']} "
                  f"价格:{trade_record['price']:.2f} 数量:{trade_record['size']}")
    
    def get_trade_records(self) -> List[Dict]:
        """获取交易记录"""
        return self.trade_records

    # =========================================
    # S1评分计算 - 卖出信号评分
    # =========================================

    def calculate_s1_score(self, indicators: Dict[str, Any], positions: Dict[str, Any]) -> tuple:
        """
        S1卖出分数计算（与天宫B1/B2策略相同）

        Args:
            indicators: 指标字典，包含:
                - close: 当前收盘价
                - high: 当前最高价
                - low: 当前最低价
                - open_price: 当前开盘价
                - close_arr: 收盘价数组
                - high_arr: 最高价数组
                - low_arr: 最低价数组
                - volume_arr: 成交量数组
                - volume: 当前成交量
                - dif: 当前DIF值
                - j: 当前J值
                - k: 当前K值
                - d: 当前D值
                - ma60: 60日均线
                - vol_ma60: 60日成交量均线
            positions: 持仓字典，包含:
                - s1_half_sold: 是否已半仓卖出
                - entry_price: 买入价格（可选）

        Returns:
            tuple: (score_s1, signal_s1_full, signal_s1_half)
                - score_s1: S1评分分数
                - signal_s1_full: 是否触发全仓卖出信号 (score > 10)
                - signal_s1_half: 是否触发半仓卖出信号 (5 < score <= 10)
        """
        close = indicators['close']
        high = indicators['high']
        low = indicators['low']
        open_price = indicators['open_price']
        close_arr = indicators['close_arr']
        high_arr = indicators['high_arr']
        low_arr = indicators['low_arr']
        volume_arr = indicators['volume_arr']
        volume = indicators['volume']
        dif = indicators['dif']
        j = indicators['j']
        k = indicators['k']
        d = indicators['d']
        ma60 = indicators['ma60']
        vol_ma60 = indicators['vol_ma60']

        s1_half_sold = positions.get('s1_half_sold', False)

        # 前10日涨幅和前50日涨幅
        前10日涨幅 = (close / close_arr[-10] - 1) * 100 > 10 if len(close_arr) >= 10 else False
        前50日涨幅 = (close / close_arr[-50] - 1) * 100 > 50 if len(close_arr) >= 50 else False

        # 条件1基础
        条件1基础 = (close < open_price) and (high == np.max(high_arr[-60:])) and (前10日涨幅 or 前50日涨幅)

        # 条件1评分
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

        # 前3天最高位距今
        if len(high_arr) >= 3:
            recent_3_high = high_arr[-3:]
            max_idx_in_recent_3 = np.argmax(recent_3_high)
            前3天最高位距今 = 2 - max_idx_in_recent_3
        else:
            前3天最高位距今 = 0

        # 条件2基础
        条件2基础 = False
        if len(high_arr) >= 60:
            hhv_h_4 = np.max(high_arr[-4:])
            hhv_h_60 = np.max(high_arr[-60:])
            if hhv_h_4 == hhv_h_60 and high != hhv_h_60:
                vol_ma5 = np.mean(volume_arr[-5:])
                vol_ma10 = np.mean(volume_arr[-10:])
                涨幅 = (close - close_arr[-2]) / close_arr[-2] * 100 if close_arr[-2] != 0 else 0
                if (volume > vol_ma5 or volume > vol_ma10) and 涨幅 < -0.03 and close < open_price and (前10日涨幅 or 前50日涨幅):
                    条件2基础 = True

        # 条件2评分
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

        # 实体和上影线
        实体 = open_price - close
        上影线 = high - max(close, open_price)

        # DIF历史计算
        dif_history = []
        for i in range(len(close_arr)):
            hist_close = close_arr[-i-1] if i < len(close_arr) else close
            hist_ema12 = hist_close
            for j_idx in range(1, min(13, i+1)):
                if i+j_idx < len(close_arr):
                    hist_ema12 = hist_ema12 * (11/13) + close_arr[-i-1-j_idx] * (2/13)

            hist_ema26 = hist_close
            for j_idx in range(1, min(27, i+1)):
                if i+j_idx < len(close_arr):
                    hist_ema26 = hist_ema26 * (25/27) + close_arr[-i-1-j_idx] * (2/27)

            hist_dif = hist_ema12 - hist_ema26
            dif_history.append(hist_dif)

        hhv_dif_60 = np.max(dif_history[-60:]) if len(dif_history) >= 60 else dif
        hhv_dif_40 = np.max(dif_history[-40:]) if len(dif_history) >= 40 else dif
        hhv_dif_20 = np.max(dif_history[-20:]) if len(dif_history) >= 20 else dif

        ref_hhv_dif_60_offset = hhv_dif_60
        ref_hhv_dif_40_offset = hhv_dif_40
        ref_hhv_dif_20_offset = hhv_dif_20

        # 加分1
        加分1 = 0
        if 条件1:
            if dif < ref_hhv_dif_60_offset:
                加分1 += 1
            if dif < ref_hhv_dif_40_offset:
                加分1 += 1
            if dif < ref_hhv_dif_20_offset:
                加分1 += 1

        # 加分2
        加分2 = 0
        if 条件1 and 上影线 > 实体 / 2 and close > close_arr[-1]:
            加分2 += 0.5
        if 条件1 and 上影线 > 实体 and close > close_arr[-1]:
            加分2 += 0.5
        if 条件1 and 上影线 > 实体 * 2 and close > close_arr[-1]:
            加分2 += 0.5

        # 加分3
        加分3 = 0
        if 条件2 and 前3天最高位距今 > 0 and len(dif_history) > 前3天最高位距今:
            该K线DIF = dif_history[前3天最高位距今] if 前3天最高位距今 < len(dif_history) else dif
            offset = 前3天最高位距今
            if len(dif_history) > 60 + offset:
                hist_hhv_dif_60_offset = np.max(dif_history[offset:offset+60]) if offset + 60 <= len(dif_history) else hhv_dif_60
            else:
                hist_hhv_dif_60_offset = hhv_dif_60

            if 该K线DIF < hist_hhv_dif_60_offset:
                加分3 = 1.8

        # 加分4
        加分4 = 0
        if 条件2 and j < k and k < d:
            加分4 = 0.8

        # 加分5
        加分5 = 0
        if (条件1 or 条件2) and close < close_arr[-1]:
            加分5 = 2

        # 加分6 - 天量柱
        天量柱 = False
        if len(volume_arr) >= 2:
            倍量柱_prev = (volume_arr[-1] > volume_arr[-2] * 1.8)
            if 倍量柱_prev and volume >= volume_arr[-1] * 1.8:
                天量柱 = True
        加分6 = 3 if 天量柱 else 0

        # 计算总分
        score_s1 = 条件1评分 + 条件2评分 + 加分1 + 加分2 + 加分3 + 加分4 + 加分5 + 加分6

        # 生成信号
        signal_s1_full = score_s1 > 10
        signal_s1_half = score_s1 > 5 and not s1_half_sold

        return (score_s1, signal_s1_full, signal_s1_half)

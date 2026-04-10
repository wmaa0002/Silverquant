"""
AIBacktestStrategy - AI回测策略

基于backtrader的回测策略，使用AI信号进行交易决策。
"""
import backtrader as bt
from typing import Dict, Any, Optional, List
from datetime import datetime


class AIBacktestStrategy(bt.Strategy):
    """AI回测策略
    
    每个bar调用AI获取交易信号，根据信号执行交易。
    缓存AI响应以避免过度调用。
    """
    
    params = dict(
        ai_analyzer=None,
        cache_days=5,
        log_level=1
    )
    
    def __init__(self):
        self.order = None
        self.ai_cache: Dict[str, tuple] = {}
        self.trade_log: List[Dict] = []
        self.last_signal: Dict[str, Any] = {}
        self.bar_count = 0
    
    def log(self, msg, dt=None):
        if self.params.log_level > 0:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'[{dt.isoformat()}] {msg}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}')
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
            self.order = None
    
    def notify_trade(self, trade):
        if trade.isclosed:
            self.log(f'TRADE PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}')
            self.trade_log.append({
                'date': self.datas[0].datetime.date(0).isoformat(),
                'type': 'sell' if trade.history[len(trade.history)-1].event == 2 else 'buy',
                'pnl': trade.pnlcomm
            })
    
    def next(self):
        if self.order:
            return
        
        self.bar_count += 1
        
        dt = self.datas[0].datetime.date(0)
        cache_key = dt.strftime('%Y-%m-%d')
        
        signal = self._get_cached_signal(cache_key)
        
        if signal is None:
            return
        
        size = self.calculate_position_size()
        
        if signal == 'BUY' and not self.position:
            self.log(f'BUY CREATE, {size} shares')
            self.order = self.buy(size=size)
            self.last_signal = {'action': 'BUY', 'date': cache_key}
        
        elif signal == 'SELL' and self.position:
            self.log(f'SELL CREATE, {size} shares')
            self.order = self.sell(size=size)
            self.last_signal = {'action': 'SELL', 'date': cache_key}
        
        elif signal == 'HOLD':
            self.log('HOLD')
            self.last_signal = {'action': 'HOLD', 'date': cache_key}
    
    def _get_cached_signal(self, cache_key: str) -> Optional[str]:
        if cache_key in self.ai_cache:
            cached_signal, cached_date = self.ai_cache[cache_key]
            days_diff = (datetime.now().date() - cached_date).days if cached_date else 999
            if days_diff < self.params.cache_days:
                return cached_signal
        
        if self.ai_analyzer is None:
            return 'HOLD'
        
        try:
            signal = self._call_ai_analyzer()
            self.ai_cache[cache_key] = (signal, datetime.now().date())
            return signal
        except Exception as e:
            self.log(f'AI call failed: {e}')
            return 'HOLD'
    
    def _call_ai_analyzer(self) -> str:
        data = self.datas[0]
        dt = data.datetime.date(0)
        close = data.close[0]
        
        prompt = f"""分析 {dt} 的交易信号。
当前价格: {close:.2f}

请给出交易信号: BUY/SELL/HOLD
只返回信号词，不要其他内容"""
        
        response = self.ai_analyzer.chat([{'role': 'user', 'content': prompt}])
        
        response = response.upper().strip()
        
        if 'BUY' in response:
            return 'BUY'
        elif 'SELL' in response:
            return 'SELL'
        else:
            return 'HOLD'
    
    def calculate_position_size(self) -> int:
        portfolio_value = self.broker.getvalue()
        price = self.datas[0].close[0]
        return int(portfolio_value * 0.95 / price / 100) * 100
    
    def get_trade_log(self) -> List[Dict]:
        return self.trade_log
    
    def get_signal_log(self) -> List[Dict]:
        return [self.last_signal]
"""
BacktestRunner - AI回测运行器

运行基于AI信号的回测，支持与买入持有对比。
"""
import backtrader as bt
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, TYPE_CHECKING
import sys
import os

if TYPE_CHECKING:
    from agent_integration.backtest.ai_strategy import AIBacktestStrategy


class BacktestRunner:
    """AI回测运行器
    
    运行AI策略回测，并与买入持有对比。
    """
    
    def __init__(self, initial_cash: float = 100000.0, commission: float = 0.0003):
        self.initial_cash = initial_cash
        self.commission = commission
        self.results: Dict[str, Any] = {}
        self.ai_results: Dict[str, Any] = {}
        self.baseline_results: Dict[str, Any] = {}
    
    def run_ai_backtest(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        ai_analyzer=None,
        cache_days: int = 5
    ) -> Dict[str, Any]:
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(self.initial_cash)
        cerebro.broker.setcommission(commission=self.commission)
        
        try:
            from agent_integration.dataflows.adapters.stock_adapter import StockDataAdapter
            adapter = StockDataAdapter()
            df = adapter.get_market_data(symbol, start_date, end_date)
            
            if df is None or len(df) == 0:
                return {'error': 'No data available'}
            
            df = df.rename(columns={
                'date': 'datetime',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
            data = bt.feeds.PandasData(dataname=df)
            cerebro.adddata(data)
            
        except Exception as e:
            return {'error': str(e)}
        
        if ai_analyzer:
            cerebro.addstrategy(
                AIBacktestStrategy,
                ai_analyzer=ai_analyzer,
                cache_days=cache_days
            )
        else:
            cerebro.addstrategy(AIBacktestStrategy, cache_days=cache_days)
        
        for analyzer in ['tradeanalyzer', 'sharperatio', 'drawdown', 'returns']:
            cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name=analyzer)
        
        results = cerebro.run()
        strat = results[0] if results else None
        
        final_value = cerebro.broker.getvalue()
        pnl = final_value - self.initial_cash
        pnl_pct = (pnl / self.initial_cash) * 100
        
        self.results = {
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'initial_cash': self.initial_cash,
            'final_value': final_value,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'trade_log': strat.get_trade_log() if strat else []
        }
        
        return self.results
    
    def compare_with_baseline(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        ai_result = self.run_ai_backtest(symbol, start_date, end_date)
        
        baseline = self._run_baseline(symbol, start_date, end_date)
        
        comparison = {
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'ai_strategy': ai_result,
            'baseline': baseline,
            'outperformance': ai_result.get('pnl_pct', 0) - baseline.get('pnl_pct', 0)
        }
        
        return comparison
    
    def _run_baseline(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        class BuyAndHold(bt.Strategy):
            def __init__(self):
                self.order = None
            
            def next(self):
                if self.order is None and not self.position:
                    self.order = self.buy()
        
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(self.initial_cash)
        
        try:
            from agent_integration.dataflows.adapters.stock_adapter import StockDataAdapter
            adapter = StockDataAdapter()
            df = adapter.get_market_data(symbol, start_date, end_date)
            
            if df is None or len(df) == 0:
                return {'error': 'No data'}
            
            df = df.rename(columns={
                'date': 'datetime',
                'close': 'close'
            })
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
            data = bt.feeds.PandasData(dataname=df)
            cerebro.adddata(data)
            
        except Exception as e:
            return {'error': str(e)}
        
        cerebro.addstrategy(BuyAndHold)
        cerebro.run()
        
        final_value = cerebro.broker.getvalue()
        pnl = final_value - self.initial_cash
        pnl_pct = (pnl / self.initial_cash) * 100
        
        return {
            'strategy': 'buy_and_hold',
            'initial_cash': self.initial_cash,
            'final_value': final_value,
            'pnl': pnl,
            'pnl_pct': pnl_pct
        }
    
    def get_results(self) -> Dict[str, Any]:
        return self.results
    
    def print_comparison(self, comparison: Dict[str, Any]):
        print("\n" + "=" * 60)
        print("回测对比结果")
        print("=" * 60)
        print(f"股票: {comparison['symbol']}")
        print(f"日期: {comparison['start_date']} ~ {comparison['end_date']}")
        print("-" * 60)
        print(f"{'策略':<20} {'收益':<15} {'收益率':<10}")
        print("-" * 60)
        ai = comparison.get('ai_strategy', {})
        base = comparison.get('baseline', {})
        print(f"{'AI策略':<20} {ai.get('pnl', 0):<15.2f} {ai.get('pnl_pct', 0):<10.2f}%")
        print(f"{'买入持有':<20} {base.get('pnl', 0):<15.2f} {base.get('pnl_pct', 0):<10.2f}%")
        print("-" * 60)
        outperf = comparison.get('outperformance', 0)
        print(f"AI超额收益: {outperf:+.2f}%")
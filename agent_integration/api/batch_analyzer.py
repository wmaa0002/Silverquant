"""
BatchAnalyzer - 批量分析器
"""
from typing import List, Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .analyzer import analyze_stock


class BatchAnalyzer:
    """批量分析器
    
    并行分析多只股票，支持进度回调和结果聚合。
    """
    
    def __init__(self, max_workers: int = 5, include_memory: bool = False):
        """初始化批量分析器
        
        Args:
            max_workers: 最大并行数
            include_memory: 是否使用记忆功能
        """
        self.max_workers = max_workers
        self.include_memory = include_memory
        self.results: List[Dict[str, Any]] = []
        self.progress = {'completed': 0, 'total': 0}
    
    def analyze(
        self,
        symbols: List[str],
        trade_date: str = None,
        progress_callback: Callable = None
    ) -> List[Dict[str, Any]]:
        """并行分析股票
        
        Args:
            symbols: 股票代码列表
            trade_date: 交易日期
            progress_callback: 进度回调 callback(completed, total, symbol, result)
            
        Returns:
            分析结果列表
        """
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y-%m-%d')
        
        self.progress = {'completed': 0, 'total': len(symbols)}
        self.results = []
        
        def analyze_one(symbol: str) -> Dict[str, Any]:
            try:
                result = analyze_stock(
                    symbol=symbol,
                    trade_date=trade_date,
                    include_memory=self.include_memory
                )
                
                self.progress['completed'] += 1
                if progress_callback:
                    progress_callback(
                        self.progress['completed'],
                        self.progress['total'],
                        symbol,
                        result
                    )
                
                return result
                
            except Exception as e:
                self.progress['completed'] += 1
                return {
                    'symbol': symbol,
                    'success': False,
                    'error': str(e)
                }
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_symbol = {
                executor.submit(analyze_one, symbol): symbol
                for symbol in symbols
            }
            
            for future in as_completed(future_to_symbol):
                try:
                    result = future.result()
                    self.results.append(result)
                except Exception as e:
                    symbol = future_to_symbol[future]
                    self.results.append({
                        'symbol': symbol,
                        'success': False,
                        'error': str(e)
                    })
        
        return self.results
    
    def get_progress(self) -> Dict[str, int]:
        """获取进度信息
        
        Returns:
            {'completed': int, 'total': int}
        """
        return self.progress.copy()
    
    def get_results(self) -> List[Dict[str, Any]]:
        """获取分析结果
        
        Returns:
            分析结果列表
        """
        return self.results
    
    def get_summary(self) -> Dict[str, Any]:
        """获取分析摘要
        
        Returns:
            {
                'total': int,
                'buy': int,
                'hold': int,
                'sell': int,
                'avg_confidence': float
            }
        """
        if not self.results:
            return {'total': 0, 'buy': 0, 'hold': 0, 'sell': 0, 'avg_confidence': 0.0}
        
        buy = sum(1 for r in self.results if r.get('final_decision') == '买入')
        hold = sum(1 for r in self.results if r.get('final_decision') == '观望')
        sell = sum(1 for r in self.results if r.get('final_decision') in ['卖出', '卖出/观望'])
        
        confidences = [r.get('confidence', 0.0) for r in self.results if r.get('success', False)]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        return {
            'total': len(self.results),
            'buy': buy,
            'hold': hold,
            'sell': sell,
            'avg_confidence': avg_conf
        }
    
    def save_results(self, filename: str, format: str = 'csv'):
        """保存结果到文件
        
        Args:
            filename: 文件路径
            format: 'csv' 或 'json'
        """
        import csv
        import json
        
        if format == 'csv':
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['symbol', 'final_decision', 'confidence', 'success'])
                writer.writeheader()
                for r in self.results:
                    writer.writerow({
                        'symbol': r.get('symbol', ''),
                        'final_decision': r.get('final_decision', ''),
                        'confidence': r.get('confidence', 0.0),
                        'success': r.get('success', False)
                    })
        elif format == 'json':
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
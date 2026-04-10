"""
批量分析示例 - batch_analysis.py

展示如何批量分析多只股票。
"""
import sys
import os
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_integration.graph.trading_graph import TradingAgentsGraph
from agent_integration.llm_adapters.factory import create_llm_by_provider
from agent_integration.api.analyzer import get_analysis_history


def analyze_batch(
    symbols: List[str],
    trade_date: str = None,
    max_workers: int = 5,
    progress_callback: Callable = None,
    include_memory: bool = False
) -> List[Dict[str, Any]]:
    """批量分析股票 (并行执行)
    
    Args:
        symbols: 股票代码列表
        trade_date: 交易日期
        max_workers: 最大并行数
        progress_callback: 进度回调函数 callback(current, total, symbol, result)
        include_memory: 是否使用记忆功能
        
    Returns:
        分析结果列表
    """
    if trade_date is None:
        trade_date = datetime.now().strftime('%Y-%m-%d')
    
    api_key = os.environ.get('DEEPSEEK_API_KEY', os.environ.get('DEEPSEEK_API_KEY', ''))
    
    try:
        llm = create_llm_by_provider(
            provider='deepseek',
            model='deepseek-chat',
            api_key=api_key
        )
    except Exception as e:
        print(f"LLM创建失败: {e}")
        
        class MockLLM:
            def chat(self, messages):
                return "Mock response"
        
        llm = MockLLM()
    
    graph = TradingAgentsGraph(llm=llm, debug=False, include_memory_context=include_memory)
    
    results = []
    completed = 0
    total = len(symbols)
    
    def analyze_one(symbol: str) -> Dict[str, Any]:
        nonlocal completed
        try:
            result = graph.propagate(
                company_of_interest=symbol,
                trade_date=trade_date
            )
            
            completed += 1
            if progress_callback:
                progress_callback(completed, total, symbol, result)
            
            return {
                'symbol': symbol,
                'decision': result.get('final_decision', 'ERROR'),
                'confidence': result.get('confidence', 0.0),
                'success': True,
                'result': result
            }
        except Exception as e:
            completed += 1
            if progress_callback:
                progress_callback(completed, total, symbol, None)
            return {
                'symbol': symbol,
                'decision': 'ERROR',
                'confidence': 0.0,
                'success': False,
                'error': str(e)
            }
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_symbol = {
            executor.submit(analyze_one, symbol): symbol
            for symbol in symbols
        }
        
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({
                    'symbol': symbol,
                    'decision': 'ERROR',
                    'confidence': 0.0,
                    'success': False,
                    'error': str(e)
                })
    
    return results


def save_to_csv(results: List[Dict[str, Any]], filename: str):
    """保存结果到CSV
    
    Args:
        results: 分析结果列表
        filename: 保存路径
    """
    import csv
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['symbol', 'decision', 'confidence', 'success'])
        writer.writeheader()
        for r in results:
            writer.writerow({
                'symbol': r.get('symbol', ''),
                'decision': r.get('decision', ''),
                'confidence': r.get('confidence', 0.0),
                'success': r.get('success', False)
            })


def save_to_json(results: List[Dict[str, Any]], filename: str):
    """保存结果到JSON
    
    Args:
        results: 分析结果列表
        filename: 保存路径
    """
    import json
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def print_summary(results: List[Dict[str, Any]]):
    """打印分析摘要"""
    print("\n" + "=" * 60)
    print("批量分析摘要")
    print("=" * 60)
    
    buy_count = sum(1 for r in results if r.get('decision') == '买入')
    hold_count = sum(1 for r in results if r.get('decision') == '观望')
    sell_count = sum(1 for r in results if r.get('decision') in ['卖出', '卖出/观望'])
    
    print(f"总股票数: {len(results)}")
    print(f"买入信号: {buy_count}")
    print(f"观望信号: {hold_count}")
    print(f"卖出信号: {sell_count}")
    
    print("\n详细信息:")
    print("-" * 60)
    print(f"{'代码':<10} {'决策':<12} {'置信度':<10}")
    print("-" * 60)
    
    for r in sorted(results, key=lambda x: -x.get('confidence', 0.0)):
        status = "✓" if r.get('success') else "✗"
        print(f"{status} {r.get('symbol', ''):<8} {r.get('decision', ''):<12} {r.get('confidence', 0.0):<10.2f}")


def default_progress_callback(current: int, total: int, symbol: str, result: Any):
    """默认进度回调"""
    if result is not None:
        decision = result.get('final_decision', 'N/A') if isinstance(result, dict) else 'N/A'
        confidence = result.get('confidence', 0.0) if isinstance(result, dict) else 0.0
        print(f"[{current}/{total}] {symbol}: ✓ {decision} ({confidence:.2f})")
    else:
        print(f"[{current}/{total}] {symbol}: ✗")


def main():
    print("=" * 60)
    print("批量分析示例")
    print("=" * 60)
    
    symbols = [
        '600519',
        '000858',
        '300750',
        '600036',
        '601318',
    ]
    
    trade_date = '2024-05-10'
    
    print(f"分析日期: {trade_date}")
    print(f"股票数量: {len(symbols)}")
    print("-" * 60)
    
    results = analyze_batch(
        symbols=symbols,
        trade_date=trade_date,
        max_workers=3,
        progress_callback=default_progress_callback,
        include_memory=False
    )
    
    print_summary(results)
    
    save = input("\n保存结果? (y/n): ")
    if save.lower() == 'y':
        filename = f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        save_to_csv(results, filename)
        print(f"已保存到 {filename}")


if __name__ == '__main__':
    main()
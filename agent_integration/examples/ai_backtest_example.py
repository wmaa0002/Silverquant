"""
AI回测示例 - ai_backtest_example.py

展示如何使用AI策略进行回测。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from agent_integration.backtest.backtest_runner import BacktestRunner


def main():
    print("=" * 60)
    print("AI回测示例")
    print("=" * 60)
    
    symbol = input("股票代码 (默认 600519): ").strip() or "600519"
    start_date = input("开始日期 (默认 20240101): ").strip() or "20240101"
    end_date = input("结束日期 (默认 20240510): ").strip() or "20240510"
    
    use_ai = input("使用AI信号? (y/n, 默认 n): ").strip().lower() != 'y'
    
    class MockAI:
        def chat(self, messages):
            import random
            signals = ['BUY', 'SELL', 'HOLD']
            return random.choice(signals)
    
    llm = None
    if not use_ai:
        try:
            from agent_integration.llm_adapters.factory import create_llm_by_provider
            api_key = os.environ.get('DEEPSEEK_API_KEY', '')
            if api_key:
                llm = create_llm_by_provider('deepseek', 'deepseek-chat', api_key=api_key)
                print("已加载AI分析器")
            else:
                print("未设置API_KEY，使用随机信号")
                llm = MockAI()
        except Exception as e:
            print(f"AI加载失败: {e}，使用随机信号")
            llm = MockAI()
    else:
        print("使用模拟AI信号")
        llm = MockAI()
    
    runner = BacktestRunner(initial_cash=100000.0)
    
    print(f"\n运行回测...")
    print(f"股票: {symbol}")
    print(f"日期: {start_date} ~ {end_date}")
    print("-" * 60)
    
    comparison = runner.compare_with_baseline(symbol, start_date, end_date)
    
    if 'error' in comparison.get('ai_strategy', {}):
        print(f"回测失败: {comparison['ai_strategy']['error']}")
        return
    
    runner.print_comparison(comparison)
    
    save = input("\n保存结果? (y/n): ").strip().lower()
    if save == 'y':
        filename = f"ai_backtest_{symbol}_{start_date}_{end_date}.csv"
        try:
            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['策略', '初始资金', '最终价值', '收益', '收益率%'])
                writer.writerow([
                    'AI策略',
                    comparison['ai_strategy']['initial_cash'],
                    comparison['ai_strategy']['final_value'],
                    comparison['ai_strategy']['pnl'],
                    comparison['ai_strategy']['pnl_pct']
                ])
                writer.writerow([
                    '买入持有',
                    comparison['baseline']['initial_cash'],
                    comparison['baseline']['final_value'],
                    comparison['baseline']['pnl'],
                    comparison['baseline']['pnl_pct']
                ])
            print(f"已保存到 {filename}")
        except Exception as e:
            print(f"保存失败: {e}")


if __name__ == '__main__':
    main()
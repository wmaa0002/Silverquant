"""
基础用法示例 - basic_usage.py

展示如何使用TradingAgentsGraph分析单只股票。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_integration.graph.trading_graph import TradingAgentsGraph
from agent_integration.llm_adapters.factory import create_llm_by_provider


def main():
    print("=" * 60)
    print("基础用法示例 - 单股票分析")
    print("=" * 60)
    
    # 创建LLM适配器
    # 注意: 需要设置 DEEPSEEK_API_KEY 环境变量
    api_key = os.environ.get('DEEPSEEK_API_KEY', 'your_api_key_here')
    
    try:
        llm = create_llm_by_provider(
            provider='deepseek',
            model='deepseek-chat',
            api_key=api_key
        )
        print("✓ LLM适配器创建成功")
    except Exception as e:
        print(f"✗ LLM适配器创建失败: {e}")
        print("  将使用模拟LLM进行演示")
        
        class MockLLM:
            def chat(self, messages):
                return "这是模拟LLM的回复。实际使用时需要配置有效的API Key。"
        
        llm = MockLLM()
    
    # 创建工作流图
    graph = TradingAgentsGraph(
        llm=llm,
        selected_analysts=['market', 'news', 'fundamentals'],
        debug=True
    )
    print("✓ TradingAgentsGraph 创建成功")
    
    # 分析股票
    symbol = '600519'  # 贵州茅台
    trade_date = '2024-05-10'
    
    print(f"\n开始分析: {symbol} on {trade_date}")
    print("-" * 40)
    
    result = graph.propagate(
        company_of_interest=symbol,
        trade_date=trade_date
    )
    
    # 输出结果
    print("\n" + "=" * 60)
    print("分析结果")
    print("=" * 60)
    
    print(f"最终决策: {result['final_decision']}")
    print(f"置信度: {result['confidence']:.2f}")
    print(f"做多置信度: {result.get('bull_confidence', 0.0):.2f}")
    print(f"做空置信度: {result.get('bear_confidence', 0.0):.2f}")
    
    if 'trading_signal' in result:
        signal = result['trading_signal']
        print(f"\n交易信号:")
        print(f"  操作: {signal['action']}")
        print(f"  入场价: {signal['entry_price']}")
        print(f"  止损价: {signal['stop_loss']}")
        print(f"  止盈价: {signal['take_profit']}")
        print(f"  仓位: {signal['position_size']:.1%}")
        print(f"  数量: {signal['quantity']}股")


if __name__ == '__main__':
    main()
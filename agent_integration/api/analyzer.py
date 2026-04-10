"""
Flask API - 股票分析接口
"""
import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_integration.adapters.config_adapter import ConfigAdapter
from agent_integration.adapters.result_adapter import ResultAdapter
from agent_integration.graph.trading_graph import TradingAgentsGraph
from agent_integration.dataflows.adapters.stock_adapter import StockDataAdapter
from agent_integration.dataflows.news.aggregator import NewsAggregator


def create_llm_with_fallback():
    """创建带降级的LLM适配器"""
    try:
        from agent_integration.llm_adapters.factory import create_llm_by_provider
        from agent_integration.adapters.config_adapter import ConfigAdapter
        
        config = ConfigAdapter()
        llm_config = config.get_llm_config(provider='minimax')
        
        llm = create_llm_by_provider(
            provider=llm_config.get('provider', 'minimax'),
            model=llm_config.get('model', 'M2'),
            api_key=llm_config.get('api_key'),
            group_id=llm_config.get('group_id'),
        )
        return llm
    except Exception as e:
        print(f"主LLM创建失败: {e}")
        return create_fallback_llm()

def create_fallback_llm():
    """创建降级LLM（返回固定响应）"""
    class FallbackLLM:
        def chat(self, messages):
            return "由于服务暂时不可用，无法完成分析。请稍后再试。"
        
        def get_token_usage(self):
            return {'input_tokens': 0, 'output_tokens': 0}
    
    return FallbackLLM()


class AnalysisError(Exception):
    """分析错误异常"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def get_llm_adapter():
    """获取LLM适配器"""
    return create_llm_with_fallback()


def analyze_stock(symbol: str, trade_date: str = None, include_memory: bool = True) -> Dict[str, Any]:
    """分析股票
    
    Args:
        symbol: 股票代码，如 '600519'
        trade_date: 交易日期，如 '2024-05-10'
        include_memory: 是否使用记忆功能
        
    Returns:
        {
            'success': bool,
            'run_id': str,
            'symbol': str,
            'trade_date': str,
            'final_decision': str,
            'confidence': float,
            'trading_signal': {...},
            'reports': {...},
            'memory_context': [...],
            'error': str
        }
    """
    if trade_date is None:
        trade_date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        llm = get_llm_adapter()
        
        if llm is None:
            return {
                'success': False,
                'symbol': symbol,
                'trade_date': trade_date,
                'error': 'LLM适配器初始化失败'
            }
        
        # 初始化记忆管理器
        memory_manager = None
        if include_memory:
            try:
                from agent_integration.memory.memory_manager import MemoryManager
                memory_manager = MemoryManager()
            except Exception as e:
                print(f"记忆功能初始化失败: {e}")
        
        graph = TradingAgentsGraph(
            llm=llm,
            debug=False,
            memory_manager=memory_manager,
            include_memory_context=include_memory and memory_manager is not None
        )
        
        stock_adapter = StockDataAdapter()
        news_aggregator = NewsAggregator()
        
        end_date = trade_date.replace('-', '')
        start_date = datetime.strptime(trade_date, '%Y-%m-%d').strftime('%Y%m%d')
        
        start_date_dt = datetime.strptime(start_date, '%Y%m%d')
        start_date_for_fetch = (start_date_dt - timedelta(days=120)).strftime('%Y%m%d')
        
        price_data = stock_adapter.get_market_data(symbol, start_date_for_fetch, end_date)
        
        news_result = news_aggregator.get_stock_news(symbol, limit=20)
        news_list = news_result.news_list if hasattr(news_result, 'news_list') else []
        
        fundamentals_data = stock_adapter.get_fundamentals(symbol)
        
        result = graph.propagate(
            company_of_interest=symbol,
            trade_date=trade_date,
            price_data=price_data,
            news_list=news_list,
            fundamentals_data=fundamentals_data
        )
        
        from agent_integration.traders.trader import Trader
        from agent_integration.agents.managers.risk_manager import RiskManager
        from agent_integration.agents.managers.research_manager import ResearchManager
        from agent_integration.agents.base import AgentConfig
        
        risk_manager = RiskManager(AgentConfig(name='risk', role='risk_manager', llm_adapter=llm))
        
        current_price = 0.0
        if price_data is not None and len(price_data) > 0:
            current_price = float(price_data.iloc[-1].get('close', 0.0))
        
        research_manager = ResearchManager(AgentConfig(name='research', role='research_manager', llm_adapter=llm))
        research_result = research_manager.conduct_research(
            symbol,
            reports=result.get('reports', {}),
            research={'bull_research': result.get('bull_research', ''), 'bear_research': result.get('bear_research', '')}
        )
        
        risk_result = risk_manager.assess_risk(
            investment_decision=research_result.get('recommendation', '观望'),
            confidence=research_result.get('confidence', 0.5),
            bull_research=result.get('bull_research', ''),
            bear_research=result.get('bear_research', ''),
            stock_code=symbol,
            current_price=current_price
        )
        
        trader = Trader()
        trading_signal = trader.generate_trading_signal(
            investment_decision=research_result.get('recommendation', '观望'),
            risk_assessment=risk_result,
            current_price=current_price,
            stock_code=symbol
        )
        
        result['research'] = research_result
        result['risk'] = risk_result
        result['trading_signal'] = trading_signal
        result['memory_context'] = result.get('memory_context', [])
        result['symbol'] = symbol
        result['trade_date'] = trade_date
        
        result_adapter = ResultAdapter()
        run_id = result_adapter.save_analysis_result(symbol, trade_date, result)
        result['run_id'] = run_id
        result['success'] = True
        
        return result
        
    except Exception as e:
        return {
            'success': False,
            'symbol': symbol,
            'trade_date': trade_date,
            'error': str(e)
        }


def get_analysis_history(symbol: str = None, start_date: str = None, end_date: str = None, offset: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    """获取分析历史
    
    Args:
        symbol: 股票代码过滤，None表示所有
        start_date: 开始日期，格式YYYY-MM-DD
        end_date: 结束日期，格式YYYY-MM-DD
        offset: 偏移量，用于分页
        limit: 返回数量限制
        
    Returns:
        分析历史列表
    """
    try:
        result_adapter = ResultAdapter()
        return result_adapter.get_analysis_history(symbol=symbol, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
    except Exception as e:
        print(f"获取分析历史失败: {e}")
        return []


def get_analysis_result(run_id: str) -> Optional[Dict[str, Any]]:
    """获取指定分析结果
    
    Args:
        run_id: 唯一标识符
        
    Returns:
        分析结果
    """
    try:
        result_adapter = ResultAdapter()
        return result_adapter.load_analysis_result(run_id)
    except Exception as e:
        print(f"获取分析结果失败: {e}")
        return None


def health_check() -> Dict[str, Any]:
    """健康检查
    
    Returns:
        健康状态
    """
    status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'components': {}
    }
    
    try:
        result_adapter = ResultAdapter()
        db = result_adapter._get_db()
        if db:
            status['components']['database'] = 'ok'
        else:
            status['components']['database'] = 'failed'
            status['status'] = 'degraded'
    except Exception:
        status['components']['database'] = 'failed'
        status['status'] = 'degraded'
    
    try:
        llm = get_llm_adapter()
        if llm:
            status['components']['llm'] = 'ok'
        else:
            status['components']['llm'] = 'failed'
            status['status'] = 'degraded'
    except Exception:
        status['components']['llm'] = 'failed'
        status['status'] = 'degraded'
    
    return status
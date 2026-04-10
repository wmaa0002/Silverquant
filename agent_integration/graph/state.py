"""
Agent状态定义 - AgentState TypedDict
"""
from typing import TypedDict, Optional, List, Dict, Any


class AgentState(TypedDict, total=False):
    """交易智能体图状态
    
    定义在智能体之间传递的状态数据结构。
    
    Attributes:
        messages: 对话历史
        company_of_interest: 关注的股票代码
        trade_date: 交易日期
        market_report: 市场分析师报告
        news_report: 新闻分析师报告
        fundamentals_report: 基本面分析师报告
        bull_research: 牛市研究员做多论点
        bear_research: 熊市研究员做空论点
        investment_decision: 投资决策
        risk_assessment: 风险评估
        final_decision: 最终交易决策 (买入/卖出/持有/观望)
        confidence: 置信度评分 (0.0-1.0)
    """
    messages: str
    company_of_interest: str
    trade_date: str
    market_report: str
    news_report: str
    fundamentals_report: str
    bull_research: str
    bear_research: str
    investment_decision: str
    risk_assessment: str
    final_decision: str
    confidence: float


def create_initial_state(company_of_interest: str, trade_date: str = '') -> AgentState:
    """创建初始状态
    
    Args:
        company_of_interest: 股票代码
        trade_date: 交易日期
        
    Returns:
        初始化的AgentState
    """
    return AgentState(
        messages='',
        company_of_interest=company_of_interest,
        trade_date=trade_date,
        market_report='',
        news_report='',
        fundamentals_report='',
        bull_research='',
        bear_research='',
        investment_decision='',
        risk_assessment='',
        final_decision='',
        confidence=0.0,
    )


def state_to_dict(state: AgentState) -> Dict[str, Any]:
    """将状态转换为字典
    
    Args:
        state: AgentState
        
    Returns:
        普通字典
    """
    return dict(state)


def merge_states(current: AgentState, updates: Dict[str, Any]) -> AgentState:
    """合并状态更新
    
    Args:
        current: 当前状态
        updates: 更新内容
        
    Returns:
        合并后的新状态
    """
    new_state = AgentState(**current)
    for key, value in updates.items():
        if key in new_state:
            new_state[key] = value
    return new_state
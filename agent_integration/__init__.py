"""
Agent Integration Module - 智能体集成模块

提供A股量化交易的智能体系统集成，包括：
- LLM适配器：支持DeepSeek、MiniMax等多种LLM提供商
- 数据流：新闻获取、情感分析、股票数据适配
- 智能体：分析师、研究员、经理等多种角色
- 工作流编排：多智能体协作图
- 交易执行：订单执行和仓位管理

主要组件：
- llm_adapters: LLM调用适配器
- dataflows: 数据处理流水线
- agents: 各类智能体实现
- graph: 智能体协作编排
- adapters: 配置和数据适配器
- traders: 交易执行
"""

__version__ = '0.1.0'

__all__ = [
    'llm_adapters',
    'dataflows',
    'agents',
    'graph',
    'adapters',
    'traders',
]

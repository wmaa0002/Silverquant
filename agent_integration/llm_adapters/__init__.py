"""
LLM Adapters Module - LLM模型适配器模块

提供统一的LLM调用接口，支持多种提供商（DeepSeek、MiniMax等）。

模块结构:
- base.py: 基础类和协议定义
- factory.py: 工厂函数，根据提供商创建适配器
- deepseek.py: DeepSeek模型适配器
- minimax.py: MiniMax模型适配器
"""

from agent_integration.llm_adapters.base import TokenTracker, OpenAICompatibleBase, get_global_token_tracker, reset_global_token_tracker
from agent_integration.llm_adapters.factory import create_llm_by_provider, create_llm_by_model
from agent_integration.llm_adapters.deepseek import ChatDeepSeek
from agent_integration.llm_adapters.minimax import ChatMiniMax

__all__ = [
    'TokenTracker',
    'OpenAICompatibleBase',
    'get_global_token_tracker',
    'reset_global_token_tracker',
    'create_llm_by_provider',
    'create_llm_by_model',
    'ChatDeepSeek',
    'ChatMiniMax',
]

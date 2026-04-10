"""
LLM适配器工厂函数 - 根据提供商创建相应的LLM适配器实例
"""
from .deepseek import ChatDeepSeek
from .minimax import ChatMiniMax
from .base import (
    OpenAICompatibleBase,
    get_global_token_tracker,
    reset_global_token_tracker,
)

PROVIDER_MAP = {
    'deepseek': ChatDeepSeek,
    'minimax': ChatMiniMax,
}

MODEL_PROVIDER_MAP = {
    'deepseek-chat': 'deepseek',
    'deepseek-coder': 'deepseek',
    'deepseek-reasoner': 'deepseek',
    'MiniMax-M2.7': 'minimax',
    'MiniMax-M2': 'minimax',
}


def create_llm_by_provider(provider: str, model: str, **kwargs) -> OpenAICompatibleBase:
    provider_lower = provider.lower()
    if provider_lower not in PROVIDER_MAP:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDER_MAP.keys())}")
    
    adapter_class = PROVIDER_MAP[provider_lower]
    return adapter_class(model=model, **kwargs)


def create_llm_by_model(model: str, **kwargs) -> OpenAICompatibleBase:
    provider = None
    model_lower = model.lower()
    
    if model in MODEL_PROVIDER_MAP:
        provider = MODEL_PROVIDER_MAP[model]
    else:
        for model_key, provider_key in MODEL_PROVIDER_MAP.items():
            if model_key in model_lower or model_lower in model_key:
                provider = provider_key
                break
    
    if provider is None:
        raise ValueError(f"Cannot determine provider for model: {model}. Please specify provider explicitly.")
    
    return create_llm_by_provider(provider, model, **kwargs)

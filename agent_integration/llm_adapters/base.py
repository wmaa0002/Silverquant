"""
LLM适配器基类 - 提供Token追踪和OpenAI兼容接口基础类
"""
import os
import time
import logging
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from abc import ABC

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun

logger = logging.getLogger(__name__)


# Token单价表 (输入/输出, 每1M tokens的价格，单位: 美元)
TOKEN_PRICE_PER_MILLION = {
    # MiniMax
    'minimax': {
        'M2': {'input': 0.5, 'output': 1.5},
        'M2.1': {'input': 0.5, 'output': 1.5},
        'M2.1-32K': {'input': 1.0, 'output': 2.0},
        'M2.1-128K': {'input': 2.0, 'output': 4.0},
    },
    # DeepSeek
    'deepseek': {
        'deepseek-chat': {'input': 0.1, 'output': 0.27},
        'deepseek-coder': {'input': 0.14, 'output': 0.42},
        'deepseek-reasoner': {'input': 0.14, 'output': 0.42},
    },
    # 阿里百炼 (Dashscope)
    'dashscope': {
        'qwen-turbo': {'input': 0.3, 'output': 0.6},
        'qwen-plus': {'input': 0.8, 'output': 2.0},
        'qwen-max': {'input': 4.0, 'output': 12.0},
        'qwen-max-long': {'input': 8.0, 'output': 24.0},
    },
    # 百度千帆 (Qianfan)
    'qianfan': {
        'ernie-3.5-8k': {'input': 0.8, 'output': 2.0},
        'ernie-3.5-128k': {'input': 1.2, 'output': 3.0},
        'ernie-4.0-8k': {'input': 4.0, 'output': 8.0},
        'ernie-4.0-8k-0329': {'input': 4.0, 'output': 8.0},
    },
    # 智谱AI (Zhipu)
    'zhipu': {
        'glm-4': {'input': 1.0, 'output': 2.0},
        'glm-4-flash': {'input': 0.1, 'output': 0.1},
        'glm-4-plus': {'input': 1.0, 'output': 3.0},
        'glm-4-long': {'input': 1.0, 'output': 2.0},
    },
    # OpenAI (参考价)
    'openai': {
        'gpt-4o': {'input': 2.5, 'output': 10.0},
        'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
        'gpt-4-turbo': {'input': 10.0, 'output': 30.0},
    },
    # Google Gemini (参考价)
    'google': {
        'gemini-1.5-pro': {'input': 1.25, 'output': 5.0},
        'gemini-1.5-flash': {'input': 0.075, 'output': 0.30},
        'gemini-2.0-flash': {'input': 0.10, 'output': 0.40},
    },
}


@dataclass
class TokenUsage:
    """单次Token使用记录"""
    timestamp: datetime
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    model: str
    provider: str


@dataclass
class TokenStats:
    """Token使用统计"""
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    request_count: int = 0
    
    # 按模型分组统计
    by_model: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # 历史记录 (最近N条)
    recent_usages: List[TokenUsage] = field(default_factory=list)
    max_recent_history: int = 100


class TokenTracker:
    """
    Token使用量追踪器
    
    用于追踪LLM调用的token使用量，支持成本计算、限额管理和统计。
    
    使用示例:
        tracker = TokenTracker()
        tracker.add_usage(prompt_tokens=100, completion_tokens=200, model='M2.1', provider='minimax')
        print(tracker.get_stats())
    """
    
    def __init__(self, max_recent_history: int = 100):
        """
        初始化Token追踪器
        
        Args:
            max_recent_history: 保留最近N条使用记录
        """
        self._stats = TokenStats(max_recent_history=max_recent_history)
        self._daily_stats: Dict[str, TokenStats] = {}  # 按日期统计
        self._lock = None  # 可选: 用于多线程安全
    
    def add_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        provider: str = 'unknown',
        metadata: Dict[str, Any] = None
    ) -> TokenUsage:
        """
        记录一次LLM调用的token使用量
        
        Args:
            prompt_tokens: 输入token数
            completion_tokens: 输出token数
            model: 模型名称
            provider: 提供商名称
            metadata: 额外元数据
            
        Returns:
            TokenUsage对象
        """
        total_tokens = prompt_tokens + completion_tokens
        
        # 计算成本
        cost = self._calculate_cost(prompt_tokens, completion_tokens, model, provider)
        
        # 创建使用记录
        usage = TokenUsage(
            timestamp=datetime.now(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            model=model,
            provider=provider
        )
        
        # 更新统计
        self._stats.total_prompt_tokens += prompt_tokens
        self._stats.total_completion_tokens += completion_tokens
        self._stats.total_tokens += total_tokens
        self._stats.total_cost += cost
        self._stats.request_count += 1
        
        # 按模型统计
        if model not in self._stats.by_model:
            self._stats.by_model[model] = {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'cost': 0.0,
                'request_count': 0
            }
        model_stats = self._stats.by_model[model]
        model_stats['prompt_tokens'] += prompt_tokens
        model_stats['completion_tokens'] += completion_tokens
        model_stats['total_tokens'] += total_tokens
        model_stats['cost'] += cost
        model_stats['request_count'] += 1
        
        # 添加到历史记录
        self._stats.recent_usages.append(usage)
        if len(self._stats.recent_usages) > self._stats.max_recent_history:
            self._stats.recent_usages.pop(0)
        
        # 按日期统计
        date_key = usage.timestamp.strftime('%Y-%m-%d')
        if date_key not in self._daily_stats:
            self._daily_stats[date_key] = TokenStats()
        daily = self._daily_stats[date_key]
        daily.total_prompt_tokens += prompt_tokens
        daily.total_completion_tokens += completion_tokens
        daily.total_tokens += total_tokens
        daily.total_cost += cost
        daily.request_count += 1
        
        logger.debug(
            f"Token usage recorded: {provider}/{model} - "
            f"prompt={prompt_tokens}, completion={completion_tokens}, "
            f"cost=${cost:.6f}"
        )
        
        return usage
    
    def _calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        provider: str
    ) -> float:
        """
        计算调用成本
        
        Args:
            prompt_tokens: 输入token数
            completion_tokens: 输出token数
            model: 模型名称
            provider: 提供商名称
            
        Returns:
            成本 (美元)
        """
        # 查找价格
        price = self._get_token_price(model, provider)
        
        if price is None:
            logger.warning(f"Unknown token price for {provider}/{model}, using 0")
            return 0.0
        
        input_cost = (prompt_tokens / 1_000_000) * price['input']
        output_cost = (completion_tokens / 1_000_000) * price['output']
        
        return input_cost + output_cost
    
    def _get_token_price(self, model: str, provider: str) -> Optional[Dict[str, float]]:
        """
        获取token价格
        
        Args:
            model: 模型名称
            provider: 提供商名称
            
        Returns:
            {'input': 价格, 'output': 价格} 或 None
        """
        provider_lower = provider.lower()
        
        if provider_lower not in TOKEN_PRICE_PER_MILLION:
            # 尝试模糊匹配
            for p in TOKEN_PRICE_PER_MILLION:
                if p in model.lower() or model.lower() in p:
                    provider_lower = p
                    break
            else:
                return None
        
        provider_prices = TOKEN_PRICE_PER_MILLION[provider_lower]
        
        # 精确匹配
        if model in provider_prices:
            return provider_prices[model]
        
        # 模糊匹配
        for m, price in provider_prices.items():
            if m in model or model in m:
                return price
        
        # 返回默认价格
        if 'default' in provider_prices:
            return provider_prices['default']
        
        return None
    
    def get_stats(self) -> TokenStats:
        """
        获取当前统计信息
        
        Returns:
            TokenStats对象
        """
        return self._stats
    
    def get_daily_stats(self, date: str = None) -> TokenStats:
        """
        获取指定日期的统计信息
        
        Args:
            date: 日期字符串 (YYYY-MM-DD)，默认为今天
            
        Returns:
            TokenStats对象
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        return self._daily_stats.get(date, TokenStats())
    
    def get_total_tokens(self) -> int:
        """获取总token使用量"""
        return self._stats.total_tokens
    
    def get_total_cost(self) -> float:
        """获取总调用成本 (美元)"""
        return self._stats.total_cost
    
    def get_request_count(self) -> int:
        """获取总请求次数"""
        return self._stats.request_count
    
    def get_cost_by_model(self) -> Dict[str, float]:
        """
        获取各模型的累计成本
        
        Returns:
            {model: cost} 字典
        """
        return {
            model: stats['cost'] 
            for model, stats in self._stats.by_model.items()
        }
    
    def reset(self):
        """重置所有统计信息"""
        self._stats = TokenStats()
        self._daily_stats.clear()
        logger.info("Token tracker reset")
    
    def reset_daily(self, date: str = None):
        """
        重置指定日期的统计信息
        
        Args:
            date: 日期字符串 (YYYY-MM-DD)，默认为今天
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        if date in self._daily_stats:
            del self._daily_stats[date]
    
    def format_stats(self) -> str:
        """
        格式化统计信息为字符串
        
        Returns:
            格式化的统计字符串
        """
        stats = self._stats
        
        lines = [
            "=" * 50,
            "Token Usage Statistics",
            "=" * 50,
            f"Total Requests:  {stats.request_count}",
            f"Total Tokens:    {stats.total_tokens:,}",
            f"  - Prompt:      {stats.total_prompt_tokens:,}",
            f"  - Completion:  {stats.total_completion_tokens:,}",
            f"Total Cost:      ${stats.total_cost:.4f}",
            "=" * 50,
        ]
        
        if self._stats.by_model:
            lines.append("\nBy Model:")
            lines.append("-" * 40)
            for model, model_stats in self._stats.by_model.items():
                lines.append(
                    f"  {model}: "
                    f"{model_stats['total_tokens']:,} tokens, "
                    f"${model_stats['cost']:.4f}"
                )
        
        return "\n".join(lines)

    def get_daily_report(self) -> Dict[str, Any]:
        """获取每日Token使用报表"""
        today = datetime.now().strftime('%Y-%m-%d')
        daily = self._daily_stats.get(today, self._create_empty_stats())

        return {
            'date': today,
            'input_tokens': daily.total_prompt_tokens,
            'output_tokens': daily.total_completion_tokens,
            'total_tokens': daily.total_tokens,
            'request_count': daily.request_count
        }

    def get_weekly_report(self) -> Dict[str, Any]:
        """获取每周Token使用报表"""
        today = datetime.now().date()
        week_ago = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        today_str = today.strftime('%Y-%m-%d')

        total_prompt = 0
        total_completion = 0
        total_tokens = 0
        total_requests = 0

        for date_key, stats in self._daily_stats.items():
            if date_key >= week_ago and date_key <= today_str:
                total_prompt += stats.total_prompt_tokens
                total_completion += stats.total_completion_tokens
                total_tokens += stats.total_tokens
                total_requests += stats.request_count

        return {
            'start_date': week_ago,
            'end_date': today_str,
            'input_tokens': total_prompt,
            'output_tokens': total_completion,
            'total_tokens': total_tokens,
            'request_count': total_requests
        }

    def check_cost_alert(self, threshold: float = 10.0) -> Optional[Dict]:
        """检查是否超过成本阈值"""
        total_cost = self.get_total_cost()

        if total_cost >= threshold:
            return {
                'alert': True,
                'threshold': threshold,
                'current_cost': total_cost,
                'percentage': (total_cost / threshold) * 100
            }
        return None

    def _create_empty_stats(self) -> TokenStats:
        """创建空的统计对象"""
        return TokenStats()


# 全局Token追踪器实例
_global_token_tracker: Optional[TokenTracker] = None


def get_global_token_tracker() -> TokenTracker:
    """
    获取全局Token追踪器实例
    
    Returns:
        TokenTracker单例
    """
    global _global_token_tracker
    if _global_token_tracker is None:
        _global_token_tracker = TokenTracker()
    return _global_token_tracker


def reset_global_token_tracker() -> None:
    """重置全局Token追踪器"""
    global _global_token_tracker
    if _global_token_tracker is not None:
        _global_token_tracker.reset()
    _global_token_tracker = None


class OpenAICompatibleBase(BaseChatModel):
    """
    OpenAI兼容接口基类
    
    提供统一的chat接口，所有LLM适配器需继承此类。
    基于LangChain的BaseChatModel，支持异步/同步调用和CallbackManager。
    
    子类必须实现:
    - _llm_type() -> str: 返回LLM类型标识
    - _generate_content() -> str: 调用实际的LLM API
    
    使用示例:
        class MyLLM(OpenAICompatibleBase):
            @property
            def _llm_type(self) -> str:
                return "my-llm"
            
            def _generate_content(self, messages, **kwargs):
                # 调用API并返回内容
                return "response content"
    """
    
    # 类级别的默认值
    provider_name: str = "unknown"
    default_model: str = "unknown"
    api_base: str = ""
    
    def __init__(
        self,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout: int = 120,
        max_retries: int = 3,
        token_tracker: TokenTracker = None,
        **kwargs
    ):
        """
        初始化LLM适配器
        
        Args:
            model: 模型名称 (默认使用类的default_model)
            api_key: API密钥 (默认从环境变量读取)
            base_url: API基础URL (默认使用类的api_base)
            temperature: 温度参数 (0.0-2.0, 越低越确定性)
            max_tokens: 最大输出token数
            timeout: 请求超时时间 (秒)
            max_retries: 最大重试次数
            token_tracker: Token追踪器实例 (默认使用全局追踪器)
            **kwargs: 其他参数传递给父类
        """
        # 调用父类初始化
        super().__init__(**kwargs)
        
        # 设置属性 (使用object.__setattr__绕过Pydantic验证)
        object.__setattr__(self, 'model', model or self.default_model)
        object.__setattr__(self, 'api_key', api_key or self._get_api_key_from_env())
        object.__setattr__(self, 'base_url', base_url or self.api_base)
        object.__setattr__(self, 'temperature', temperature)
        object.__setattr__(self, 'max_tokens', max_tokens)
        object.__setattr__(self, 'timeout', timeout)
        object.__setattr__(self, 'max_retries', max_retries)
        
        # Token追踪器
        if token_tracker is not None:
            self._token_tracker = token_tracker
        else:
            try:
                self._token_tracker = get_global_token_tracker()
            except Exception:
                self._token_tracker = TokenTracker()
        
        # 初始化请求计数器
        self._request_count = 0
    
    def _get_api_key_from_env(self) -> str:
        """
        从环境变量获取API密钥
        
        Returns:
            API密钥字符串
        """
        # 子类可以重写此方法
        env_var = f"{self.provider_name.upper()}_API_KEY"
        return os.environ.get(env_var, "")
    
    @property
    def _llm_type(self) -> str:
        """返回LLM类型标识"""
        return f"chat_{self.provider_name}"
    
    @property
    def name(self) -> str:
        """返回适配器名称"""
        return f"Chat{self.provider_name.title().replace('_', '')}"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> ChatResult:
        """
        同步生成响应 (LangChain接口)
        
        Args:
            messages: 消息列表
            stop: 停止词列表
            run_manager: 回调管理器
            **kwargs: 其他参数
            
        Returns:
            ChatResult对象
        """
        try:
            # 转换消息格式
            formatted_messages = self._convert_messages(messages)
            
            # 调用API (带重试)
            response_text = self._call_with_retry(
                formatted_messages,
                stop=stop,
                **kwargs
            )
            
            # 解析token使用量
            usage = self._parse_usage_from_response(response_text, **kwargs)
            
            # 记录token使用
            if usage:
                self._token_tracker.add_usage(
                    prompt_tokens=usage.get('prompt_tokens', 0),
                    completion_tokens=usage.get('completion_tokens', 0),
                    model=self.model,
                    provider=self.provider_name
                )
            
            # 创建返回结果
            generation = ChatGeneration(message=AIMessage(content=response_text))
            return ChatResult(generations=[generation])
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> ChatResult:
        """
        异步生成响应 (LangChain接口)
        
        Args:
            messages: 消息列表
            stop: 停止词列表
            run_manager: 回调管理器
            **kwargs: 其他参数
            
        Returns:
            ChatResult对象
        """
        import asyncio
        
        try:
            # 转换消息格式
            formatted_messages = self._convert_messages(messages)
            
            # 异步调用API
            response_text = await asyncio.to_thread(
                self._call_with_retry,
                formatted_messages,
                stop=stop,
                **kwargs
            )
            
            # 解析token使用量
            usage = self._parse_usage_from_response(response_text, **kwargs)
            
            # 记录token使用
            if usage:
                self._token_tracker.add_usage(
                    prompt_tokens=usage.get('prompt_tokens', 0),
                    completion_tokens=usage.get('completion_tokens', 0),
                    model=self.model,
                    provider=self.provider_name
                )
            
            # 创建返回结果
            generation = ChatGeneration(message=AIMessage(content=response_text))
            return ChatResult(generations=[generation])
            
        except Exception as e:
            logger.error(f"Async LLM generation failed: {e}")
            raise
    
    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """
        将LangChain消息格式转换为API所需格式
        
        Args:
            messages: LangChain消息列表
            
        Returns:
            [{'role': 'user', 'content': '...'}] 格式的列表
        """
        result = []
        for msg in messages:
            role = self._get_role_from_message(msg)
            content = msg.content
            result.append({'role': role, 'content': content})
        return result
    
    def _get_role_from_message(self, message: BaseMessage) -> str:
        """
        从LangChain消息获取角色
        
        Args:
            message: LangChain消息
            
        Returns:
            'user', 'assistant', 或 'system'
        """
        if isinstance(message, HumanMessage):
            return 'user'
        elif isinstance(message, AIMessage):
            return 'assistant'
        elif isinstance(message, SystemMessage):
            return 'system'
        else:
            return 'user'
    
    def _call_with_retry(
        self,
        messages: List[Dict[str, str]],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        带重试的API调用
        
        Args:
            messages: 消息列表
            stop: 停止词列表
            **kwargs: 其他参数
            
        Returns:
            响应文本
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                self._request_count += 1
                
                # 调用实际生成方法
                response = self._generate_content(messages, stop=stop, **kwargs)
                
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"API call attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )
                
                # 指数退避
                if attempt < self.max_retries - 1:
                    import random
                    sleep_time = (2 ** attempt) * 0.5 + random.uniform(0, 0.5)
                    time.sleep(sleep_time)
        
        # 所有重试都失败
        logger.error(f"All {self.max_retries} attempts failed. Last error: {last_error}")
        raise last_error
    
    def _generate_content(
        self,
        messages: List[Dict[str, str]],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        调用实际的LLM API生成内容
        
        此方法需要子类实现。
        
        Args:
            messages: 消息列表
            stop: 停止词列表
            **kwargs: 其他参数
            
        Returns:
            响应文本
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _generate_content()"
        )
    
    def _parse_usage_from_response(
        self,
        response_text: str,
        **kwargs
    ) -> Optional[Dict[str, int]]:
        """
        从API响应中解析token使用量
        
        默认实现返回None，子类可重写以提供准确的token统计。
        
        Args:
            response_text: 响应文本
            **kwargs: 其他参数
            
        Returns:
            {'prompt_tokens': N, 'completion_tokens': M} 或 None
        """
        # 默认使用估算: 输出token约为响应长度的1/4
        if response_text:
            estimated_completion = len(response_text) // 4
            # 如果子类有更准确的方法，应该重写
            return {
                'prompt_tokens': 0,  # 需要子类提供准确值
                'completion_tokens': max(1, estimated_completion)
            }
        return None
    
    def get_token_usage(self) -> Dict[str, Any]:
        """
        获取当前token使用情况
        
        Returns:
            {total_tokens, total_cost, request_count, ...}
        """
        return {
            'total_tokens': self._token_tracker.get_total_tokens(),
            'total_cost': self._token_tracker.get_total_cost(),
            'request_count': self._request_count,
            'model': self.model,
            'provider': self.provider_name
        }
    
    def get_token_stats(self) -> Dict[str, Any]:
        """
        获取详细的Token使用统计
        
        Returns:
            {
                'total_tokens': int,
                'total_cost': float,
                'request_count': int,
                'prompt_tokens': int,
                'completion_tokens': int,
                'by_model': dict,
                'daily_stats': dict
            }
        """
        stats = self._token_tracker.get_stats()
        return {
            'total_tokens': stats.total_tokens,
            'total_cost': stats.total_cost,
            'request_count': stats.request_count,
            'prompt_tokens': stats.total_prompt_tokens,
            'completion_tokens': stats.total_completion_tokens,
            'by_model': stats.by_model,
            'recent_usages': [
                {
                    'timestamp': u.timestamp.isoformat(),
                    'tokens': u.total_tokens,
                    'cost': u.cost,
                    'model': u.model
                }
                for u in stats.recent_usages[-10:]
            ]
        }
    
    def chat(
        self,
        messages: Union[List[BaseMessage], List[str], str],
        **kwargs
    ) -> str:
        """
        简单的chat接口 (同步)
        
        Args:
            messages: 消息列表或字符串
            **kwargs: 其他参数传递给_generate
                
        Returns:
            响应文本
        """
        # 转换字符串/列表/字典为BaseMessage
        if isinstance(messages, str):
            messages = [HumanMessage(content=messages)]
        elif isinstance(messages, list) and messages:
            converted = []
            for msg in messages:
                if isinstance(msg, str):
                    converted.append(HumanMessage(content=msg))
                elif isinstance(msg, dict):
                    # 支持 {'role': 'user', 'content': '...'}
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if role == 'system':
                        converted.append(SystemMessage(content=content))
                    elif role == 'assistant':
                        converted.append(AIMessage(content=content))
                    else:
                        converted.append(HumanMessage(content=content))
                elif isinstance(msg, BaseMessage):
                    converted.append(msg)
            messages = converted
        
        # 调用生成
        result = self._generate(messages, **kwargs)
        return result.generations[0].message.content
    
    async def achat(
        self,
        messages: Union[List[BaseMessage], List[str], str],
        **kwargs
    ) -> str:
        """
        简单的chat接口 (异步)
        
        Args:
            messages: 消息列表或字符串
            **kwargs: 其他参数传递给_agenerate
                
        Returns:
            响应文本
        """
        # 转换字符串/列表为BaseMessage
        if isinstance(messages, str):
            messages = [HumanMessage(content=messages)]
        elif isinstance(messages, list) and messages:
            if isinstance(messages[0], str):
                messages = [HumanMessage(content=m) for m in messages]
        
        # 异步调用生成
        result = await self._agenerate(messages, **kwargs)
        return result.generations[0].message.content

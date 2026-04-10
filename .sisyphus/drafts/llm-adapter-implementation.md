# LLM适配层详细实现方案

> **生成时间**: 2026-03-29
> **模块**: agent_integration/llm_adapters/

---

## 1. LLM适配层概览

### 1.1 支持的LLM提供商

| 提供商 | 模型示例 | 上下文长度 | 函数调用 | API Key |
|--------|----------|------------|----------|---------|
| **DeepSeek** | deepseek-chat, deepseek-coder | 32K | ✅ | deepseek_api_key |
| **阿里百炼** | qwen-turbo, qwen-plus, qwen-max | 8K-32K | ✅ | dashscope_api_key |
| **百度千帆** | ernie-3.5-8k, ernie-4.0-8k | 5K-8K | ✅ | qianfan_api_key |
| **智谱AI** | glm-4, glm-4-plus, glm-3-turbo | 128K-200K | ✅ | zhipu_api_key |
| **Google** | gemini-1.5-pro, gemini-1.5-flash | 1M | ✅ | google_api_key |
| **OpenAI** | gpt-4o, gpt-4-turbo, gpt-3.5-turbo | 128K | ✅ | openai_api_key |
| **Anthropic** | claude-3.5-sonnet, claude-3-opus | 200K | ✅ | anthropic_api_key |
| **SiliconFlow** | deepseek-xxx, qwen-xxx | 32K | ✅ | siliconflow_api_key |
| **OpenRouter** | anthropic/claude-3.5, openai/gpt-4 | 200K | ✅ | openrouter_api_key |
| **Ollama** | llama3, qwen2, mistral | 本地 | ❌ | 无需Key |
| **MiniMax** | M2, M2.1, abab6.5s | 32K-128K | ✅ | minimax_api_key |

### 1.2 适配器架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Adapter Architecture                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TradingAgentsGraph                                              │
│       │                                                         │
│       ▼                                                         │
│  create_llm_by_provider()  ◄── 工厂函数                         │
│       │                                                         │
│       ▼                                                         │
│  ┌────┴────┬──────────┬──────────┬──────────┐                   │
│  │         │          │          │          │                    │
│  ▼         ▼          ▼          ▼          ▼                    │
│ Base       DeepSeek  DashScope  Qianfan   Zhipu                  │
│ Adapter   Adapter    Adapter   Adapter    Adapter                  │
│   │          │         │         │         │                     │
│   └──────────┴─────────┴─────────┴─────────┘                     │
│                    │                                              │
│                    ▼                                              │
│            OpenAICompatibleBase ◄── 统一基类                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 统一适配器基类

### 2.1 OpenAICompatibleBase

```python
# agent_integration/llm_adapters/base.py

import os
import time
import logging
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime
from functools import wraps

from langchain.chat_models.base import BaseChatModel
from langchain.schema import ChatResult, ChatGeneration, AIMessage, HumanMessage, SystemMessage
from langchain.callbacks.manager import CallbackManagerForLLMRun

logger = logging.getLogger(__name__)

class TokenTracker:
    """Token使用追踪器"""
    
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.request_count = 0
        self.cost = 0.0
        
        # 价格表 (每1M tokens)
        self.PRICE_PER_MILLION = {
            'deepseek': {'input': 0.1, 'output': 0.1},  # $0.1/M
            'gpt-4o': {'input': 5.0, 'output': 15.0},
            'gpt-4-turbo': {'input': 10.0, 'output': 30.0},
            'claude-3.5-sonnet': {'input': 3.0, 'output': 15.0},
            'qwen-plus': {'input': 0.8, 'output': 2.0},
            'glm-4': {'input': 0.5, 'output': 1.5},
            'minimax': {'input': 0.5, 'output': 1.5},  # MiniMax价格
        }
    
    def track(self, usage_metadata: Dict, model: str):
        """记录token使用"""
        self.total_tokens += usage_metadata.get('total_tokens', 0)
        self.prompt_tokens += usage_metadata.get('input_tokens', 0)
        self.completion_tokens += usage_metadata.get('output_tokens', 0)
        self.request_count += 1
        
        # 计算成本
        model_prices = self.PRICE_PER_MILLION.get(model, {'input': 0, 'output': 0})
        self.cost += (
            self.prompt_tokens / 1_000_000 * model_prices['input'] +
            self.completion_tokens / 1_000_000 * model_prices['output']
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_tokens': self.total_tokens,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'request_count': self.request_count,
            'estimated_cost': self.cost,
        }
    
    def reset(self):
        """重置计数器"""
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.request_count = 0
        self.cost = 0.0


class OpenAICompatibleBase(BaseChatModel):
    """
    OpenAI兼容接口的LLM基类
    
    所有支持的LLM提供商都继承此类，
    只需实现 _create_message_dicts 和 _convert_response 方法。
    """
    
    # 类属性 (子类必须设置)
    provider_name: str = "base"
    default_model: str = "base"
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_env_var: str = None,  # 环境变量名
        base_url: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = 60.0,
        max_retries: int = 3,
        token_tracker: Optional[TokenTracker] = None,
        **kwargs
    ):
        """
        初始化LLM适配器
        
        Args:
            model: 模型名称 (默认使用类默认值)
            api_key: API密钥 (默认从环境变量读取)
            api_key_env_var: API密钥环境变量名
            base_url: API base URL
            temperature: 温度参数
            max_tokens: 最大token数
            timeout: 请求超时 (秒)
            max_retries: 最大重试次数
            token_tracker: Token追踪器
        """
        super().__init__(**kwargs)
        
        self.model = model or self.default_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.token_tracker = token_tracker or TokenTracker()
        
        # 获取API Key
        if api_key:
            self.api_key = api_key
        elif api_key_env_var:
            self.api_key = os.environ.get(api_key_env_var, '')
            if not self.api_key:
                logger.warning(f"环境变量 {api_key_env_var} 未设置")
        else:
            self.api_key = ''
        
        self.base_url = base_url
        
        # 子类覆盖
        self._setup_api()
    
    def _setup_api(self):
        """子类实现: 设置API端点"""
        raise NotImplementedError
    
    @property
    def _invocation_params(self) -> Dict[str, Any]:
        """返回调用参数"""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
    
    def _generate(
        self,
        messages: List[Union[HumanMessage, SystemMessage, AIMessage]],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> ChatResult:
        """
        同步生成 (LangChain调用入口)
        """
        # 将LangChain消息转换为API格式
        message_dicts = self._convert_messages(messages)
        
        # 调用API
        start_time = time.time()
        response = self._call_with_retry(
            messages=message_dicts,
            stop=stop,
            **kwargs
        )
        
        # 追踪Token
        elapsed = time.time() - start_time
        if hasattr(response, 'usage_metadata'):
            self.token_tracker.track(response.usage_metadata, self.model)
        
        # 转换响应
        generations = self._convert_response(response)
        
        return ChatResult(generations=generations)
    
    async def _agenerate(
        self,
        messages: List[Union[HumanMessage, SystemMessage, AIMessage]],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> ChatResult:
        """异步生成"""
        import asyncio
        
        # 将LangChain消息转换为API格式
        message_dicts = self._convert_messages(messages)
        
        # 异步调用
        start_time = time.time()
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._call_with_retry(messages=message_dicts, stop=stop, **kwargs)
        )
        
        elapsed = time.time() - start_time
        if hasattr(response, 'usage_metadata'):
            self.token_tracker.track(response.usage_metadata, self.model)
        
        # 转换响应
        generations = self._convert_response(response)
        
        return ChatResult(generations=generations)
    
    def _call_with_retry(
        self,
        messages: List[Dict],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> Any:
        """带重试的API调用"""
        import requests
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}',
                }
                
                payload = {
                    'model': self.model,
                    'messages': messages,
                    'temperature': self.temperature,
                }
                
                if self.max_tokens:
                    payload['max_tokens'] = self.max_tokens
                if stop:
                    payload['stop'] = stop
                
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                    **kwargs
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # Rate limit, 指数退避
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limit, 等待 {wait_time} 秒")
                    time.sleep(wait_time)
                    continue
                else:
                    response.raise_for_status()
                    
            except Exception as e:
                last_error = e
                logger.warning(f"API调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                continue
        
        raise last_error or Exception("API调用失败")
    
    def _convert_messages(self, messages: List) -> List[Dict]:
        """将LangChain消息转换为API格式"""
        result = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                role = 'system'
                content = msg.content
            elif isinstance(msg, HumanMessage):
                role = 'user'
                content = msg.content
            elif isinstance(msg, AIMessage):
                role = 'assistant'
                content = msg.content
            else:
                role = 'user'
                content = str(msg.content)
            
            result.append({'role': role, 'content': content})
        return result
    
    def _convert_response(self, response: Dict) -> List[ChatGeneration]:
        """将API响应转换为LangChain格式"""
        choices = response.get('choices', [])
        generations = []
        
        for choice in choices:
            message = choice.get('message', {})
            content = message.get('content', '')
            
            gen = ChatGeneration(
                message=AIMessage(content=content),
                generation_info=dict(choice)
            )
            generations.append(gen)
        
        return generations
    
    def get_token_usage(self) -> Dict[str, Any]:
        """获取Token使用统计"""
        return self.token_tracker.get_stats()
```

---

## 3. DeepSeek适配器

### 3.1 配置

```python
# agent_integration/llm_adapters/deepseek.py

from typing import Optional
from .base import OpenAICompatibleBase, TokenTracker

class ChatDeepSeek(OpenAICompatibleBase):
    """
    DeepSeek Chat模型适配器
    
    API文档: https://platform.deepseek.com/docs/api
    
    模型:
    - deepseek-chat: 通用对话 (32K上下文)
    - deepseek-coder: 代码模型
    """
    
    provider_name = "deepseek"
    default_model = "deepseek-chat"
    
    # DeepSeek API端点
    API_BASE = "https://api.deepseek.com/v1"
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        token_tracker: Optional[TokenTracker] = None,
        **kwargs
    ):
        super().__init__(
            model=model,
            api_key=api_key,
            api_key_env_var='DEEPSEEK_API_KEY',
            base_url=self.API_BASE,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            token_tracker=token_tracker,
            **kwargs
        )
    
    def _setup_api(self):
        """设置DeepSeek API"""
        # DeepSeek兼容OpenAI格式，无需额外设置
        pass
```

---

## 4. 阿里百炼 (DashScope) 适配器

### 4.1 配置

```python
# agent_integration/llm_adapters/dashscope.py

from typing import Optional, Dict, Any
from .base import OpenAICompatibleBase, TokenTracker

class ChatDashScope(OpenAICompatibleBase):
    """
    阿里百炼 DashScope 模型适配器
    
    API文档: https://help.aliyun.com/zh/dashscope/
    
    模型:
    - qwen-turbo: 快速模型 (8K上下文)
    - qwen-plus: 高性能 (32K上下文)
    - qwen-max: 最大模型 (8K上下文)
    - qwen-max-longcontext: 长上下文 (128K)
    """
    
    provider_name = "dashscope"
    default_model = "qwen-plus"
    
    # DashScope API端点
    API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        token_tracker: Optional[TokenTracker] = None,
        **kwargs
    ):
        super().__init__(
            model=model,
            api_key=api_key,
            api_key_env_var='DASHSCOPE_API_KEY',
            base_url=self.API_BASE,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            token_tracker=token_tracker,
            **kwargs
        )
    
    def _setup_api(self):
        """设置DashScope API"""
        # 阿里百炼也兼容OpenAI格式
        pass
    
    def _call_with_retry(
        self,
        messages: list,
        stop: Optional[list] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        重写: DashScope使用不同的错误处理
        """
        import requests
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}',
                }
                
                payload = {
                    'model': self.model,
                    'messages': messages,
                    'temperature': self.temperature,
                }
                
                if self.max_tokens:
                    payload['max_tokens'] = self.max_tokens
                if stop:
                    payload['stop'] = stop
                
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                    **kwargs
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 400:
                    # 参数错误
                    error = response.json()
                    error_code = error.get('error', {}).get('code', '')
                    if error_code == 'invalid_parameter':
                        raise ValueError(f"参数错误: {error}")
                    raise ValueError(f"请求错误: {error}")
                elif response.status_code == 401:
                    raise ValueError("API Key无效")
                elif response.status_code == 429:
                    # Rate limit
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Rate limit, 等待 {wait_time} 秒")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 500:
                    # 服务器错误, 重试
                    self.logger.warning(f"服务器错误 (尝试 {attempt + 1})")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    response.raise_for_status()
                    
            except Exception as e:
                last_error = e
                if isinstance(e, ValueError):
                    raise  # 不重试参数错误
                self.logger.warning(f"API调用失败: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                continue
        
        raise last_error or Exception("API调用失败")
```

---

## 5. 百度千帆 (QianFan) 适配器

### 5.1 配置

```python
# agent_integration/llm_adapters/qianfan.py

from typing import Optional, Dict, Any
from .base import OpenAICompatibleBase, TokenTracker
import base64
import time

class ChatQianFan(OpenAICompatibleBase):
    """
    百度千帆 QianFan 模型适配器
    
    API文档: https://cloud.baidu.com/doc/WenxinWorkshop/s/Wm2x4gfw9
    
    模型:
    - ernie-3.5-8k: ERNIE 3.5 (8K上下文)
    - ernie-4.0-8k: ERNIE 4.0 (8K上下文)
    - ernie-3.5-128k: 长上下文
    """
    
    provider_name = "qianfan"
    default_model = "ernie-3.5-8k"
    
    # QianFan API端点
    API_BASE = "https://qianfan.baidubce.com/v2/chat/completions"
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,  # 百度使用AK/SK认证
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        token_tracker: Optional[TokenTracker] = None,
        **kwargs
    ):
        self.secret_key = secret_key or os.environ.get('QIANFAN_SECRET_KEY', '')
        self._access_token = None
        self._token_expires_at = 0
        
        super().__init__(
            model=model,
            api_key=api_key,
            api_key_env_var='QIANFAN_API_KEY',
            base_url=self.API_BASE,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            token_tracker=token_tracker,
            **kwargs
        )
    
    def _setup_api(self):
        """设置百度千帆API (AK/SK认证)"""
        # 百度需要使用AK/SK获取Access Token
        pass
    
    def _get_access_token(self) -> str:
        """获取Access Token (百度鉴权)"""
        import os
        
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token
        
        # 使用AK/SK获取Token
        auth_url = "https://qianfan.baidubce.com/oauth/2.0/token"
        params = {
            'grant_type': 'client_credentials',
            'client_id': self.api_key,
            'client_secret': self.secret_key,
        }
        
        import requests
        response = requests.post(auth_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            self._access_token = data.get('access_token', '')
            expires_in = data.get('expires_in', 2592000)  # 默认30天
            self._token_expires_at = now + expires_in - 300  # 提前5分钟过期
            return self._access_token
        else:
            raise ValueError(f"获取Access Token失败: {response.text}")
    
    def _call_with_retry(
        self,
        messages: list,
        stop: Optional[list] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        重写: 百度使用Access Token认证
        """
        import requests
        
        last_error = None
        access_token = self._get_access_token()
        
        for attempt in range(self.max_retries):
            try:
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {access_token}',
                }
                
                payload = {
                    'model': self.model,
                    'messages': messages,
                    'temperature': self.temperature,
                }
                
                if self.max_tokens:
                    payload['max_tokens'] = self.max_tokens
                if stop:
                    payload['stop'] = stop
                
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                    **kwargs
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    # Token过期, 重新获取
                    self._access_token = None
                    access_token = self._get_access_token()
                    continue
                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Rate limit, 等待 {wait_time} 秒")
                    time.sleep(wait_time)
                    continue
                else:
                    response.raise_for_status()
                    
            except Exception as e:
                last_error = e
                self.logger.warning(f"API调用失败: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                continue
        
        raise last_error or Exception("API调用失败")
```

---

## 6. 智谱AI (Zhipu) 适配器

### 6.1 配置

```python
# agent_integration/llm_adapters/zhipu.py

from typing import Optional, Dict, Any
from .base import OpenAICompatibleBase, TokenTracker

class ChatZhipu(OpenAICompatibleBase):
    """
    智谱AI Zhipu 模型适配器
    
    API文档: https://open.bigmodel.cn/dev/api
    
    模型:
    - glm-4: 高性能 (128K上下文)
    - glm-4-plus: 增强版
    - glm-3-turbo: 快速模型
    """
    
    provider_name = "zhipu"
    default_model = "glm-4"
    
    # 智谱AI API端点
    API_BASE = "https://open.bigmodel.cn/api/paas/v4"
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        token_tracker: Optional[TokenTracker] = None,
        **kwargs
    ):
        super().__init__(
            model=model,
            api_key=api_key,
            api_key_env_var='ZHIPU_API_KEY',
            base_url=self.API_BASE,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            token_tracker=token_tracker,
            **kwargs
        )
    
    def _setup_api(self):
        """设置智谱AI API"""
        # 智谱AI兼容OpenAI格式
        pass
```

---

## 7. Google Gemini 适配器

### 7.1 配置

```python
# agent_integration/llm_adapters/google.py

from typing import Optional, Dict, Any, List, Union
from .base import OpenAICompatibleBase, TokenTracker
from langchain.schema import HumanMessage, AIMessage, SystemMessage

class ChatGoogle(OpenAICompatibleBase):
    """
    Google Gemini 模型适配器
    
    API文档: https://ai.google.dev/docs
    
    模型:
    - gemini-1.5-pro: 高性能 (1M上下文)
    - gemini-1.5-flash: 快速模型
    - gemini-1.0-pro: 标准模型
    """
    
    provider_name = "google"
    default_model = "gemini-1.5-pro"
    
    # Google AI API端点
    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: float = 120.0,  # Gemini可能较慢
        max_retries: int = 3,
        token_tracker: Optional[TokenTracker] = None,
        **kwargs
    ):
        super().__init__(
            model=model,
            api_key=api_key,
            api_key_env_var='GOOGLE_API_KEY',
            base_url=self.API_BASE,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            token_tracker=token_tracker,
            **kwargs
        )
    
    def _setup_api(self):
        """设置Google AI API"""
        # API URL需要包含模型名
        self.api_url = f"{self.base_url}/{self.model}:generateContent"
    
    def _convert_messages(self, messages: List) -> str:
        """
        重写: Gemini使用不同的消息格式
        """
        # Gemini将多轮对话合并为一个prompt
        prompt_parts = []
        
        for msg in messages:
            if isinstance(msg, SystemMessage):
                prompt_parts.append(f"[系统] {msg.content}")
            elif isinstance(msg, HumanMessage):
                prompt_parts.append(f"[用户] {msg.content}")
            elif isinstance(msg, AIMessage):
                prompt_parts.append(f"[助手] {msg.content}")
        
        return "\n".join(prompt_parts)
    
    def _call_with_retry(
        self,
        messages: List[Dict],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        重写: Gemini API格式
        """
        import requests
        
        last_error = None
        prompt = self._convert_messages_from_dicts(messages)
        
        for attempt in range(self.max_retries):
            try:
                headers = {
                    'Content-Type': 'application/json',
                }
                
                payload = {
                    'contents': [{
                        'parts': [{'text': prompt}]
                    }],
                    'generationConfig': {
                        'temperature': self.temperature,
                    }
                }
                
                if self.max_tokens:
                    payload['generationConfig']['maxOutputTokens'] = self.max_tokens
                
                url = f"{self.api_url}?key={self.api_key}"
                
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                    **kwargs
                )
                
                if response.status_code == 200:
                    return self._convert_gemini_response(response.json())
                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Rate limit, 等待 {wait_time} 秒")
                    time.sleep(wait_time)
                    continue
                else:
                    response.raise_for_status()
                    
            except Exception as e:
                last_error = e
                self.logger.warning(f"API调用失败: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                continue
        
        raise last_error or Exception("API调用失败")
    
    def _convert_messages_from_dicts(self, messages: List[Dict]) -> str:
        """将消息字典转换为文本"""
        prompt_parts = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'system':
                prompt_parts.append(f"[系统] {content}")
            elif role == 'user':
                prompt_parts.append(f"[用户] {content}")
            elif role == 'assistant':
                prompt_parts.append(f"[助手] {content}")
        return "\n".join(prompt_parts)
    
    def _convert_gemini_response(self, response: Dict) -> Dict:
        """将Gemini响应转换为OpenAI格式"""
        candidates = response.get('candidates', [])
        
        if not candidates:
            return {
                'choices': [{
                    'message': {'content': ''},
                    'finish_reason': 'STOP'
                }],
                'usage_metadata': response.get('usageMetadata', {}),
            }
        
        content = candidates[0]['content']['parts'][0]['text']
        finish_reason = candidates[0].get('finishReason', 'STOP')
        
        return {
            'choices': [{
                'message': {'content': content},
                'finish_reason': finish_reason
            }],
            'usage_metadata': response.get('usageMetadata', {}),
        }
```

---

## 8. MiniMax 适配器

### 8.1 配置

```python
# agent_integration/llm_adapters/minimax.py

from typing import Optional, Dict, Any
from .base import OpenAICompatibleBase, TokenTracker

class ChatMiniMax(OpenAICompatibleBase):
    """
    MiniMax 模型适配器
    
    API文档: https://platform.minimax.io/docs/api-reference/text-chat
    
    模型:
    - M2: 通用对话模型
    - M2.1: 增强版对话模型
    - abab6.5s: 高速模型
    - abab6.5g: 游戏模型
    """
    
    provider_name = "minimax"
    default_model = "M2"
    
    # MiniMax API端点 (兼容OpenAI格式)
    API_BASE = "https://api.minimax.io/v1"
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        group_id: Optional[str] = None,  # MiniMax需要group_id
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        token_tracker: Optional[TokenTracker] = None,
        **kwargs
    ):
        self.group_id = group_id or os.environ.get('MINIMAX_GROUP_ID', '')
        if not self.group_id:
            import logging
            logging.warning("MiniMax group_id未设置，部分功能可能受限")
        
        super().__init__(
            model=model,
            api_key=api_key,
            api_key_env_var='MINIMAX_API_KEY',
            base_url=self.API_BASE,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            token_tracker=token_tracker,
            **kwargs
        )
    
    def _setup_api(self):
        """设置MiniMax API"""
        # MiniMax兼容OpenAI格式，但需要group_id
        pass
    
    def _call_with_retry(
        self,
        messages: List[Dict],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        重写: MiniMax API调用
        """
        import requests
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}',
                }
                
                payload = {
                    'model': self.model,
                    'messages': messages,
                    'temperature': self.temperature,
                }
                
                if self.max_tokens:
                    payload['max_tokens'] = self.max_tokens
                if stop:
                    payload['stop'] = stop
                
                # MiniMax特殊参数
                if self.group_id:
                    payload['group_id'] = self.group_id
                
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                    **kwargs
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # MiniMax返回格式与OpenAI略有不同，需要转换
                    return self._convert_minimax_response(result)
                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Rate limit, 等待 {wait_time} 秒")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 400:
                    error = response.json()
                    raise ValueError(f"MiniMax API错误: {error}")
                else:
                    response.raise_for_status()
                    
            except Exception as e:
                last_error = e
                self.logger.warning(f"API调用失败: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                continue
        
        raise last_error or Exception("API调用失败")
    
    def _convert_minimax_response(self, response: Dict) -> Dict:
        """将MiniMax响应转换为OpenAI兼容格式"""
        choices = response.get('choices', [])
        
        if not choices:
            return {
                'choices': [{
                    'message': {'content': ''},
                    'finish_reason': 'STOP'
                }],
                'usage_metadata': response.get('usage', {}),
            }
        
        first_choice = choices[0]
        message = first_choice.get('message', {})
        content = message.get('content', '')
        finish_reason = first_choice.get('finish_reason', 'STOP')
        
        return {
            'choices': [{
                'message': {'content': content},
                'finish_reason': finish_reason
            }],
            'usage_metadata': response.get('usage', {}),
        }
```

---

## 9. 工厂函数

### 8.1 LLM工厂

```python
# agent_integration/llm_adapters/factory.py

import os
from typing import Optional, Dict, Any, List
from langchain.chat_models.base import BaseChatModel

from .base import TokenTracker, OpenAICompatibleBase
from .deepseek import ChatDeepSeek
from .dashscope import ChatDashScope
from .qianfan import ChatQianFan
from .zhipu import ChatZhipu
from .google import ChatGoogle
from .minimax import ChatMiniMax

# 提供商映射
PROVIDER_MAP = {
    'deepseek': ChatDeepSeek,
    'dashscope': ChatDashScope,
    'qianfan': ChatQianFan,
    'zhipu': ChatZhipu,
    'google': ChatGoogle,
    'minimax': ChatMiniMax,
    # 别名
    'baidu': ChatQianFan,
    'ali': ChatDashScope,
    'alibaba': ChatDashScope,
    'qwen': ChatDashScope,
    'zhipuai': ChatZhipu,
}

# 模型到提供商的映射
MODEL_PROVIDER_MAP = {
    # DeepSeek
    'deepseek-chat': 'deepseek',
    'deepseek-coder': 'deepseek',
    # DashScope
    'qwen-turbo': 'dashscope',
    'qwen-plus': 'dashscope',
    'qwen-max': 'dashscope',
    # QianFan
    'ernie-3.5-8k': 'qianfan',
    'ernie-4.0-8k': 'qianfan',
    # Zhipu
    'glm-4': 'zhipu',
    'glm-4-plus': 'zhipu',
    'glm-3-turbo': 'zhipu',
    # Google
    'gemini-1.5-pro': 'google',
    'gemini-1.5-flash': 'google',
    'gemini-1.0-pro': 'google',
    # MiniMax
    'M2': 'minimax',
    'M2.1': 'minimax',
    'abab6.5s': 'minimax',
    'abab6.5g': 'minimax',
}

def create_llm_by_provider(
    provider: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    timeout: float = 60.0,
    max_retries: int = 3,
    token_tracker: Optional[TokenTracker] = None,
    **kwargs
) -> BaseChatModel:
    """
    根据提供商名称创建LLM实例
    
    Args:
        provider: 提供商名称 (deepseek, dashscope, qianfan, zhipu, google)
        model: 模型名称 (可选, 使用默认值)
        api_key: API密钥 (可选, 从环境变量读取)
        base_url: API端点 (可选)
        temperature: 温度参数
        max_tokens: 最大token数
        timeout: 请求超时
        max_retries: 最大重试次数
        token_tracker: Token追踪器
        
    Returns:
        BaseChatModel: LangChain兼容的Chat模型
        
    Examples:
        # 使用DeepSeek
        llm = create_llm_by_provider('deepseek', 'deepseek-chat')
        
        # 使用阿里百炼
        llm = create_llm_by_provider('dashscope', 'qwen-plus')
        
        # 使用智谱AI
        llm = create_llm_by_provider('zhipu', 'glm-4')
    """
    provider = provider.lower()
    
    # 获取provider类
    if provider not in PROVIDER_MAP:
        available = ', '.join(PROVIDER_MAP.keys())
        raise ValueError(
            f"未知的LLM提供商: {provider}\n"
            f"支持的提供商: {available}"
        )
    
    llm_class = PROVIDER_MAP[provider]
    
    # 创建实例
    return llm_class(
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
        token_tracker=token_tracker,
        **kwargs
    )

def create_llm_by_model(
    model: str,
    api_key: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    token_tracker: Optional[TokenTracker] = None,
    **kwargs
) -> BaseChatModel:
    """
    根据模型名称自动选择提供商并创建LLM实例
    
    Args:
        model: 模型名称 (会自动识别提供商)
        api_key: API密钥
        temperature: 温度参数
        max_tokens: 最大token数
        token_tracker: Token追踪器
        
    Examples:
        llm = create_llm_by_model('deepseek-chat')
        llm = create_llm_by_model('qwen-plus')
        llm = create_llm_by_model('glm-4')
    """
    # 查找提供商
    provider = MODEL_PROVIDER_MAP.get(model)
    
    if not provider:
        raise ValueError(
            f"无法识别模型对应的提供商: {model}\n"
            f"请使用 create_llm_by_provider() 并指定 provider"
        )
    
    return create_llm_by_provider(
        provider=provider,
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        token_tracker=token_tracker,
        **kwargs
    )

def create_llm_with_fallback(
    primary: Dict[str, str],
    fallback: Dict[str, str],
    token_tracker: Optional[TokenTracker] = None,
    **kwargs
) -> BaseChatModel:
    """
    创建带降级的LLM (主提供商失败时自动切换)
    
    Args:
        primary: {'provider': 'deepseek', 'model': 'deepseek-chat'}
        fallback: {'provider': 'dashscope', 'model': 'qwen-plus'}
        token_tracker: Token追踪器
    """
    # 先尝试主提供商
    try:
        return create_llm_by_provider(
            **primary,
            token_tracker=token_tracker,
            **kwargs
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"主提供商 {primary['provider']} 失败: {e}, 切换到备用")
        
        return create_llm_by_provider(
            **fallback,
            token_tracker=token_tracker,
            **kwargs
        )

# 全局Token追踪器
_global_token_tracker = TokenTracker()

def get_global_token_tracker() -> TokenTracker:
    """获取全局Token追踪器"""
    return _global_token_tracker

def reset_global_token_tracker():
    """重置全局Token追踪器"""
    _global_token_tracker.reset()
```

---

## 9. 目录结构

```
agent_integration/llm_adapters/
├── __init__.py
│
├── base.py              # OpenAICompatibleBase基类 + TokenTracker
├── factory.py           # 工厂函数
│
├── deepseek.py          # DeepSeek适配器
├── dashscope.py         # 阿里百炼适配器
├── qianfan.py           # 百度千帆适配器
├── zhipu.py             # 智谱AI适配器
├── google.py            # Google Gemini适配器
│
└── utils.py             # 工具函数
```

---

## 10. 使用示例

### 10.1 基础使用

```python
from agent_integration.llm_adapters import create_llm_by_provider

# 使用DeepSeek
llm = create_llm_by_provider(
    provider='deepseek',
    model='deepseek-chat',
    temperature=0.1
)

# 使用MiniMax
llm = create_llm_by_provider(
    provider='minimax',
    model='M2.1',
    temperature=0.1
)

# 调用
from langchain.schema import HumanMessage
response = llm([HumanMessage(content="分析一下贵州茅台的投資价值")])
print(response.content)
```

### 10.2 带Token追踪

```python
from agent_integration.llm_adapters import (
    create_llm_by_provider, 
    get_global_token_tracker
)

# 创建带追踪的LLM
tracker = get_global_token_tracker()
llm = create_llm_by_provider(
    provider='deepseek',
    model='deepseek-chat',
    token_tracker=tracker
)

# 使用
response = llm([HumanMessage(content="...")])

# 查看使用量
stats = tracker.get_stats()
print(f"总Token: {stats['total_tokens']}")
print(f"费用: ${stats['estimated_cost']:.4f}")
```

### 10.3 带降级

```python
from agent_integration.llm_adapters import create_llm_with_fallback

llm = create_llm_with_fallback(
    primary={'provider': 'deepseek', 'model': 'deepseek-chat'},
    fallback={'provider': 'dashscope', 'model': 'qwen-plus'}
)
```

### 10.4 集成到TradingAgentsGraph

```python
from agent_integration.llm_adapters import create_llm_by_provider
from agent_integration.graph import TradingAgentsGraph

# 创建LLM
fast_llm = create_llm_by_provider('deepseek', 'deepseek-chat')
reasoning_llm = create_llm_by_provider('deepseek', 'deepseek-chat')

# 创建多智能体图
graph = TradingAgentsGraph(
    fast_llm=fast_llm,
    reasoning_llm=reasoning_llm,
    selected_analysts=['market', 'news', 'fundamentals']
)

# 执行分析
result = graph.propagate('600519', '2024-05-10')
```

---

## 11. 环境变量配置

```bash
# .env 或 ~/.bash_profile

# DeepSeek
DEEPSEEK_API_KEY=sk-xxxx

# 阿里百炼
DASHSCOPE_API_KEY=sk-xxxx

# 百度千帆
QIANFAN_API_KEY=xxxx
QIANFAN_SECRET_KEY=xxxx

# 智谱AI
ZHIPU_API_KEY=xxxx

# Google
GOOGLE_API_KEY=xxxx

# OpenAI (可选)
OPENAI_API_KEY=sk-xxxx

# MiniMax
MINIMAX_API_KEY=xxxx
MINIMAX_GROUP_ID=xxxx
```

---

## 12. 后续优化

### 12.1 短期优化

- [ ] 添加Anthropic Claude适配器
- [ ] 添加SiliconFlow/OpenRouter适配器
- [ ] 添加Ollama本地模型支持

### 12.2 中期优化

- [ ] 支持流式输出 (Streaming)
- [ ] 支持函数调用 (Function Calling)
- [ ] 添加对话历史管理

### 12.3 长期优化

- [ ] 支持多模态 (图像输入)
- [ ] 实现自动模型选择 (根据任务类型)
- [ ] 构建成本优化策略

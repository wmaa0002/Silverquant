"""
MiniMax LLM适配器 - ChatMiniMax模型适配器实现
"""
import os
import requests
from typing import List, Dict, Optional, Any, ClassVar

from pydantic import ConfigDict

from agent_integration.llm_adapters.base import OpenAICompatibleBase


class ChatMiniMax(OpenAICompatibleBase):
    """MiniMax模型聊天适配器"""
    
    provider_name: ClassVar[str] = "minimax"
    default_model: ClassVar[str] = "MiniMax-M2.7"
    api_base: ClassVar[str] = "https://api.minimaxi.com/v1"
    
    model_config: ClassVar[ConfigDict] = ConfigDict(extra='allow')
    
    def __init__(
        self,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        temperature: float = 1,
        max_tokens: int = 4096,
        timeout: int = 120,
        max_retries: int = 3,
        group_id: str = None,
        token_tracker=None,
        **kwargs
    ):
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            token_tracker=token_tracker,
            **kwargs
        )
        self.group_id = group_id or self._get_group_id_from_env()
        self._last_usage: Optional[Dict[str, int]] = None
    
    def _get_api_key_from_env(self) -> str:
        return os.environ.get("MINIMAX_API_KEY", "")
    
    def _get_group_id_from_env(self) -> str:
        return os.environ.get("MINIMAX_GROUP_ID", "")
    
    @property
    def _llm_type(self) -> str:
        return f"chat_{self.provider_name}"
    
    def _generate_content(
        self,
        messages: List[Dict[str, str]],
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
        }
        # group_id is optional, only add if not empty
        if self.group_id:
            payload["group_id"] = self.group_id
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if "messages" in choice and len(choice["messages"]) > 0:
                content = choice["messages"][0].get("content", "")
            elif "message" in choice:
                content = choice["message"].get("content", "")
            else:
                content = ""
        else:
            content = ""
        
        if "usage" in data:
            self._last_usage = {
                "prompt_tokens": data["usage"].get("prompt_tokens", 0),
                "completion_tokens": data["usage"].get("completion_tokens", 0)
            }
        
        return content
    
    def _parse_usage_from_response(
        self,
        response_text: str,
        **kwargs
    ) -> Optional[Dict[str, int]]:
        if self._last_usage is not None:
            usage = self._last_usage.copy()
            self._last_usage = None
            return usage
        return None
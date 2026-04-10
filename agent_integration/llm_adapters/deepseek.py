"""
DeepSeek LLM适配器 - ChatDeepSeek模型适配器实现
"""
import requests
from typing import ClassVar
from agent_integration.llm_adapters.base import OpenAICompatibleBase


class ChatDeepSeek(OpenAICompatibleBase):
    provider_name: ClassVar[str] = "deepseek"
    default_model: ClassVar[str] = "deepseek-chat"
    api_base: ClassVar[str] = "https://api.deepseek.com/v1"

    def __init__(self, api_key: str = None, model: str = None, **kwargs):
        base_url = kwargs.pop('base_url', None)
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **kwargs
        )
        self._last_usage = None

    def _get_api_key_from_env(self) -> str:
        return super()._get_api_key_from_env()

    @property
    def _llm_type(self) -> str:
        return f"chat_{self.provider_name}"

    def _generate_content(
        self,
        messages,
        stop=None,
        **kwargs
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages
        }
        if stop:
            payload["stop"] = stop
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        if self.temperature:
            payload["temperature"] = self.temperature

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        self._last_usage = data.get("usage")

        return data["choices"][0]["message"]["content"]

    def _parse_usage_from_response(self, response_text: str, **kwargs):
        if self._last_usage:
            return {
                'prompt_tokens': self._last_usage.get('prompt_tokens', 0),
                'completion_tokens': self._last_usage.get('completion_tokens', 0)
            }
        return None

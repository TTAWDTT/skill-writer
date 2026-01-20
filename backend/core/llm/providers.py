"""
LLM Providers
支持多种 LLM 服务商的统一接口
"""
from abc import ABC, abstractmethod
from typing import Optional, AsyncGenerator, List
import httpx

from .config_store import LLMConfig, LLMProviderType, get_llm_config


class LLMProvider(ABC):
    """LLM Provider 基类"""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def chat(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> str:
        """同步聊天"""
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """流式聊天"""
        pass


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容 API Provider"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=config.api_key or "dummy",  # Some providers don't need API key
            base_url=config.base_url,
        )

    async def chat(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    async def chat_stream(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GoogleGeminiProvider(LLMProvider):
    """Google AI Studio (Gemini) Provider"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.api_key = config.api_key

    def _convert_messages(self, messages: List[dict]) -> dict:
        """转换消息格式为 Gemini 格式"""
        contents = []
        system_instruction = None

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        result = {"contents": contents}
        if system_instruction:
            result["system_instruction"] = {"parts": [{"text": system_instruction}]}

        return result

    async def chat(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> str:
        url = f"{self.base_url}/models/{self.config.model}:generateContent"

        payload = self._convert_messages(messages)
        payload["generationConfig"] = {
            "temperature": temperature or self.config.temperature,
            "maxOutputTokens": max_tokens,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                params={"key": self.api_key},
                headers={"Content-Type": "application/json"},
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

            # 提取响应文本
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return ""

    async def chat_stream(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/models/{self.config.model}:streamGenerateContent"

        payload = self._convert_messages(messages)
        payload["generationConfig"] = {
            "temperature": temperature or self.config.temperature,
            "maxOutputTokens": max_tokens,
        }

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                json=payload,
                params={"key": self.api_key, "alt": "sse"},
                headers={"Content-Type": "application/json"},
                timeout=120.0,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json
                        try:
                            data = json.loads(line[6:])
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    text = parts[0].get("text", "")
                                    if text:
                                        yield text
                        except json.JSONDecodeError:
                            continue


class GitHubCopilotProvider(LLMProvider):
    """GitHub Copilot Provider"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.github_token = config.github_token
        self._copilot_token = None

    async def _get_copilot_token(self) -> str:
        """获取 Copilot API Token"""
        if self._copilot_token:
            return self._copilot_token

        async with httpx.AsyncClient() as client:
            # 使用 GitHub Token 获取 Copilot Token
            response = await client.get(
                "https://api.github.com/copilot_internal/v2/token",
                headers={
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/json",
                    "Editor-Version": "vscode/1.85.0",
                    "Editor-Plugin-Version": "copilot/1.155.0",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            self._copilot_token = data.get("token")
            return self._copilot_token

    async def chat(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> str:
        token = await self._get_copilot_token()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.githubcopilot.com/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "temperature": temperature or self.config.temperature,
                    "max_tokens": max_tokens,
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Editor-Version": "vscode/1.85.0",
                    "Copilot-Integration-Id": "vscode-chat",
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        token = await self._get_copilot_token()

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                "https://api.githubcopilot.com/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "temperature": temperature or self.config.temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Editor-Version": "vscode/1.85.0",
                    "Copilot-Integration-Id": "vscode-chat",
                },
                timeout=120.0,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json
                        try:
                            if line.strip() == "data: [DONE]":
                                break
                            data = json.loads(line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue


def get_llm_client(config: Optional[LLMConfig] = None) -> LLMProvider:
    """根据配置获取 LLM Provider"""
    if config is None:
        config = get_llm_config()

    if config.provider == LLMProviderType.GOOGLE_GEMINI:
        return GoogleGeminiProvider(config)
    elif config.provider == LLMProviderType.GITHUB_COPILOT:
        return GitHubCopilotProvider(config)
    else:
        return OpenAICompatibleProvider(config)


# 全局 LLM 客户端缓存
_llm_client: Optional[LLMProvider] = None


def get_global_llm_client() -> LLMProvider:
    """获取全局 LLM 客户端"""
    global _llm_client
    if _llm_client is None:
        _llm_client = get_llm_client()
    return _llm_client


def reset_llm_client():
    """重置 LLM 客户端（配置变更后调用）"""
    global _llm_client
    _llm_client = None

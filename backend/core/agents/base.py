"""
Agent 基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncGenerator

from backend.core.llm.providers import get_llm_client, LLMProvider
from backend.core.llm.config_store import get_llm_config


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(self, llm_client: Optional[LLMProvider] = None):
        self._llm_client = llm_client

    @property
    def client(self) -> LLMProvider:
        """获取 LLM 客户端（延迟初始化）"""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    @property
    def model(self) -> str:
        """获取当前模型名称"""
        config = get_llm_config()
        return config.model

    @property
    def temperature(self) -> float:
        """获取当前温度设置"""
        config = get_llm_config()
        return config.temperature

    async def _chat(
        self,
        messages: list,
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> str:
        """调用 LLM"""
        return await self.client.chat(
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens,
        )

    async def _chat_stream(
        self,
        messages: list,
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """流式调用 LLM"""
        async for chunk in self.client.chat_stream(
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        """执行 Agent 任务"""
        pass

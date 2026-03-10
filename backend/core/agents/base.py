"""
Agent 基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncGenerator

from backend.core.llm.gateway import LLMGateway, get_global_gateway
from backend.core.llm.config_store import get_llm_config


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(self, llm_gateway: Optional[LLMGateway] = None):
        # Allow dependency injection for testing or custom routing.
        self._llm_gateway = llm_gateway

    @property
    def gateway(self) -> LLMGateway:
        """获取 LLM Gateway（延迟初始化）"""
        if self._llm_gateway is None:
            self._llm_gateway = get_global_gateway()
        return self._llm_gateway

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
        return await self.gateway.chat(messages, temperature=temperature, max_tokens=max_tokens)

    async def _chat_stream(
        self,
        messages: list,
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """流式调用 LLM"""
        async for chunk in self.gateway.chat_stream(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        """执行 Agent 任务"""
        pass

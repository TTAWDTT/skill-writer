"""
LLM Gateway

Thin wrapper around provider selection + config hot-reload so that
Agents / workflows only depend on this module instead of concrete
providers or config_store.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, AsyncGenerator, List

from .config_store import get_llm_config, LLMConfig
from .providers import get_llm_client, LLMProvider


def _fingerprint_from_config(cfg: LLMConfig) -> tuple:
    """
    Build a lightweight fingerprint of the active LLM configuration.

    This is used to detect when a user changes provider/base_url/model/api_key
    so that we can transparently refresh the underlying provider client.
    """
    return (
        str(cfg.provider),
        cfg.provider_name,
        cfg.base_url,
        cfg.model,
        cfg.image_model,
        cfg.api_key,
        cfg.github_token,
    )


@dataclass
class LLMGateway:
    """
    High-level entrypoint for all LLM calls in the app.

    - Handles lazy initialization of the concrete provider.
    - Refreshes provider instance when LLM configuration changes.
    - Exposes a simple chat / chat_stream interface for Agents.
    """

    _client: Optional[LLMProvider] = None
    _fingerprint: Optional[tuple] = None

    def _current_config(self) -> LLMConfig:
        return get_llm_config()

    def _ensure_client(self) -> LLMProvider:
        cfg = self._current_config()
        fp = _fingerprint_from_config(cfg)
        if self._client is None or self._fingerprint != fp:
            self._client = get_llm_client(cfg)
            self._fingerprint = fp
        return self._client

    @property
    def config(self) -> LLMConfig:
        """Expose the current config when callers need read-only access."""
        return self._current_config()

    async def chat(
        self,
        messages: List[dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> str:
        client = self._ensure_client()
        cfg = self._current_config()
        temp = temperature if temperature is not None else cfg.temperature
        return await client.chat(messages, temperature=temp, max_tokens=max_tokens)

    async def chat_stream(
        self,
        messages: List[dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        client = self._ensure_client()
        cfg = self._current_config()
        temp = temperature if temperature is not None else cfg.temperature
        async for chunk in client.chat_stream(messages, temperature=temp, max_tokens=max_tokens):
            yield chunk


_gateway: Optional[LLMGateway] = None


def get_global_gateway() -> LLMGateway:
    """Return the process-wide LLM gateway instance."""
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway


def reset_global_gateway() -> None:
    """Reset the global gateway (used when config has been changed explicitly)."""
    global _gateway
    _gateway = None


"""
LLM Providers
支持多种 LLM 服务商的统一接口
"""
from abc import ABC, abstractmethod
from typing import Optional, AsyncGenerator, List
import httpx
import logging
import time
import asyncio
import os
import random

from .config_store import LLMConfig, LLMProviderType, get_llm_config

logger = logging.getLogger(__name__)

# 全局节流：避免短时间内并发/突发请求导致 429
_llm_request_lock = asyncio.Lock()
_llm_last_request_ts = 0.0
_LLM_MIN_INTERVAL_S = float(os.getenv("LLM_MIN_INTERVAL_S", "0.35"))
_GEMINI_MIN_INTERVAL_S = float(os.getenv("GEMINI_MIN_INTERVAL_S", "0.9"))

async def _pace_llm_request(min_interval_s: float = _LLM_MIN_INTERVAL_S):
    """Global pacing to reduce bursty traffic across providers."""
    global _llm_last_request_ts
    async with _llm_request_lock:
        now = time.time()
        wait_s = min_interval_s - (now - _llm_last_request_ts)
        if wait_s > 0:
            await asyncio.sleep(wait_s)
        _llm_last_request_ts = time.time()


async def _retry_httpx(
    request_fn,
    *,
    max_attempts: int = 6,
    timeout_s: float = 120.0,
    pace_interval_s: float = _LLM_MIN_INTERVAL_S,
):
    """
    Retry helper for httpx requests.
    - Retries 429 with Retry-After or exponential backoff + jitter
    - Retries transient 5xx / network timeouts
    """
    last_exc = None
    for attempt in range(max_attempts):
        try:
            await _pace_llm_request(pace_interval_s)
            return await request_fn(timeout_s)
        except httpx.HTTPStatusError as e:
            last_exc = e
            status = e.response.status_code
            if status == 429:
                retry_after = e.response.headers.get("retry-after") or e.response.headers.get("Retry-After")
                try:
                    retry_after_s = float(retry_after) if retry_after else None
                except Exception:
                    retry_after_s = None

                base = min(30.0, 2.0 * (2 ** attempt))
                jitter = random.uniform(0.0, 0.6)
                sleep_s = retry_after_s if retry_after_s is not None else (base + jitter)
                logger.warning("[llm] http 429 retry attempt=%s/%s sleep=%.1fs", attempt + 1, max_attempts, sleep_s)
                await asyncio.sleep(sleep_s)
                continue

            if 500 <= status <= 599:
                sleep_s = min(10.0, 0.8 * (2 ** attempt)) + random.uniform(0.0, 0.4)
                logger.warning("[llm] http %s retry attempt=%s/%s sleep=%.1fs", status, attempt + 1, max_attempts, sleep_s)
                await asyncio.sleep(sleep_s)
                continue
            raise
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadError) as e:
            last_exc = e
            sleep_s = min(10.0, 0.8 * (2 ** attempt)) + random.uniform(0.0, 0.4)
            logger.warning("[llm] httpx transient retry attempt=%s/%s sleep=%.1fs type=%s", attempt + 1, max_attempts, sleep_s, type(e).__name__)
            await asyncio.sleep(sleep_s)
            continue
    raise last_exc  # type: ignore[misc]


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
            timeout=httpx.Timeout(120.0, connect=20.0),
        )

    async def _with_retry(self, fn, *, max_attempts: int = 6):
        from openai import RateLimitError, APITimeoutError, APIConnectionError, InternalServerError, APIStatusError

        last_error = None
        for attempt in range(max_attempts):
            try:
                # Serialize + pace requests across the whole app to reduce bursts.
                await _pace_llm_request(_LLM_MIN_INTERVAL_S)
                return await fn()
            except (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError, APIStatusError) as e:
                last_error = e

                status_code = getattr(e, "status_code", None)
                is_rate_limited = isinstance(e, RateLimitError) or status_code == 429

                # Backoff strategy
                if is_rate_limited:
                    retry_after = None
                    resp = getattr(e, "response", None)
                    if resp is not None:
                        retry_after = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
                    try:
                        retry_after_s = float(retry_after) if retry_after else None
                    except Exception:
                        retry_after_s = None

                    # exponential backoff with jitter, capped
                    base = min(30.0, 2.0 * (2 ** attempt))
                    jitter = random.uniform(0.0, 0.6)
                    sleep_s = retry_after_s if retry_after_s is not None else (base + jitter)

                    logger.warning(
                        "[llm] rate limited attempt=%s/%s sleep=%.1fs msg=%s",
                        attempt + 1,
                        max_attempts,
                        sleep_s,
                        str(e)[:200],
                    )
                    await asyncio.sleep(sleep_s)
                    continue

                # Other transient errors
                logger.warning(
                    "[llm] transient error attempt=%s/%s type=%s msg=%s",
                    attempt + 1,
                    max_attempts,
                    type(e).__name__,
                    str(e)[:200],
                )
                await asyncio.sleep(0.8 * (2 ** attempt))
        raise last_error  # type: ignore[misc]

    async def chat(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> str:
        start = time.time()
        logger.info(
            "[llm] openai_compatible chat model=%s base_url=%s api_key=%s",
            self.config.model,
            self.config.base_url,
            f"len={len(self.config.api_key)}" if self.config.api_key else "empty",
        )
        async def _call():
            return await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens,
            )

        response = await self._with_retry(_call)
        logger.info("[llm] openai_compatible chat ok %.2fs", time.time() - start)
        return response.choices[0].message.content

    async def chat_stream(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        async def _call():
            return await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens,
                stream=True,
            )

        stream = await self._with_retry(_call)
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GoogleGeminiProvider(LLMProvider):
    """Google AI Studio (Gemini) Provider"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or "https://generativelanguage.googleapis.com/v1beta"
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
            async def _do(timeout_s: float):
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": self.api_key,
                        "x-goog-api-client": "skillwriter/0.1",
                    },
                    timeout=timeout_s,
                )
                resp.raise_for_status()
                return resp

            response = await _retry_httpx(
                _do,
                max_attempts=6,
                timeout_s=120.0,
                pace_interval_s=_GEMINI_MIN_INTERVAL_S,
            )
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

        import json as json_module

        async with httpx.AsyncClient() as client:
            # For streaming, retry only the initial request establishment on 429/5xx/timeouts.
            for attempt in range(6):
                try:
                    await _pace_llm_request(_GEMINI_MIN_INTERVAL_S)
                    async with client.stream(
                        "POST",
                        url,
                        json=payload,
                        params={"alt": "sse"},
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": self.api_key,
                            "x-goog-api-client": "skillwriter/0.1",
                        },
                        timeout=120.0,
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    data = json_module.loads(line[6:])
                                    candidates = data.get("candidates", [])
                                    if candidates:
                                        parts = candidates[0].get("content", {}).get("parts", [])
                                        if parts:
                                            text = parts[0].get("text", "")
                                            if text:
                                                yield text
                                except json_module.JSONDecodeError:
                                    continue
                        return
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    if status == 429:
                        retry_after = e.response.headers.get("retry-after") or e.response.headers.get("Retry-After")
                        try:
                            retry_after_s = float(retry_after) if retry_after else None
                        except Exception:
                            retry_after_s = None
                        base = min(30.0, 2.0 * (2 ** attempt))
                        jitter = random.uniform(0.0, 0.6)
                        sleep_s = retry_after_s if retry_after_s is not None else (base + jitter)
                        logger.warning("[llm] gemini stream 429 retry attempt=%s/6 sleep=%.1fs", attempt + 1, sleep_s)
                        await asyncio.sleep(sleep_s)
                        continue
                    if 500 <= status <= 599:
                        sleep_s = min(10.0, 0.8 * (2 ** attempt)) + random.uniform(0.0, 0.4)
                        logger.warning("[llm] gemini stream %s retry attempt=%s/6 sleep=%.1fs", status, attempt + 1, sleep_s)
                        await asyncio.sleep(sleep_s)
                        continue
                    raise
                except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadError) as e:
                    sleep_s = min(10.0, 0.8 * (2 ** attempt)) + random.uniform(0.0, 0.4)
                    logger.warning("[llm] gemini stream transient retry attempt=%s/6 sleep=%.1fs type=%s", attempt + 1, sleep_s, type(e).__name__)
                    await asyncio.sleep(sleep_s)
                    continue


class GitHubCopilotProvider(LLMProvider):
    """GitHub Copilot Provider"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.github_token = config.github_token
        self._copilot_token = None
        self._token_expires_at = 0

    async def _get_copilot_token(self, force_refresh: bool = False) -> str:
        """获取 Copilot API Token"""
        import time

        # 检查 Token 是否存在且未过期（提前 60 秒刷新）
        if not force_refresh and self._copilot_token and time.time() < self._token_expires_at - 60:
            return self._copilot_token

        async with httpx.AsyncClient() as client:
            try:
                # 使用 GitHub OAuth Token 获取 Copilot Token
                response = await client.get(
                    "https://api.github.com/copilot_internal/v2/token",
                    headers={
                        "Authorization": f"token {self.github_token}",
                        "Accept": "application/json",
                        "Editor": "vscode",
                        "Editor-Version": "vscode/1.95.0",
                        "Editor-Plugin-Version": "copilot/1.245.0",
                        "User-Agent": "SkillWriter (github_copilot provider)",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                try:
                    data = e.response.json()
                except Exception:
                    data = None

                if status == 401:
                    raise Exception("GitHub Token 无效或已过期，请在设置中重新登录 GitHub。") from e

                if status == 403:
                    notification_id = None
                    if isinstance(data, dict):
                        notification_id = (data.get("error_details") or {}).get("notification_id")
                    if notification_id == "feature_flag_blocked":
                        raise Exception(
                            "GitHub 已阻止通过当前方式获取 Copilot Token（feature_flag_blocked）。"
                            "这通常意味着该实现依赖的内部接口在你的账号/环境下不可用；建议改用 DeepSeek / OpenAI 兼容服务商。"
                        ) from e

                    message = None
                    if isinstance(data, dict):
                        message = data.get("message") or data.get("error") or data.get("error_description")
                    raise Exception(f"GitHub Copilot Token 获取失败（403）：{message or e.response.text}") from e

                raise Exception(f"GitHub Copilot Token 获取失败（HTTP {status}）：{e.response.text}") from e

            data = response.json()
            token = data.get("token")
            if not token:
                raise Exception("GitHub Copilot Token 获取失败：响应中缺少 token。")

            self._copilot_token = token
            # Token 通常有 expires_at 字段，如果没有则默认 30 分钟
            self._token_expires_at = data.get("expires_at", time.time() + 1800)
            return token

    async def _make_request(self, messages: List[dict], temperature: float, max_tokens: int, stream: bool = False):
        """发起 API 请求，带自动重试"""
        token = await self._get_copilot_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Editor-Version": "vscode/1.95.0",
            "Copilot-Integration-Id": "vscode-chat",
        }

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stream:
            payload["stream"] = True

        return headers, payload

    async def chat(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> str:
        temp = temperature or self.config.temperature

        for attempt in range(2):  # 最多重试一次
            headers, payload = await self._make_request(messages, temp, max_tokens, stream=False)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.githubcopilot.com/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120.0,
                )

                if response.status_code == 401 and attempt == 0:
                    # Token 过期，强制刷新后重试
                    await self._get_copilot_token(force_refresh=True)
                    continue

                response.raise_for_status()
                data = response.json()

                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""

        raise Exception("GitHub Copilot API 认证失败，请重新登录 GitHub")

    async def chat_stream(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        import json as json_module

        temp = temperature or self.config.temperature
        headers, payload = await self._make_request(messages, temp, max_tokens, stream=True)

        async with httpx.AsyncClient() as client:
            try:
                async with client.stream(
                    "POST",
                    "https://api.githubcopilot.com/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120.0,
                ) as response:
                    if response.status_code == 401:
                        # Token 过期，刷新并重试
                        await self._get_copilot_token(force_refresh=True)
                        headers, payload = await self._make_request(messages, temp, max_tokens, stream=True)
                        async with client.stream(
                            "POST",
                            "https://api.githubcopilot.com/chat/completions",
                            json=payload,
                            headers=headers,
                            timeout=120.0,
                        ) as retry_response:
                            retry_response.raise_for_status()
                            async for line in retry_response.aiter_lines():
                                if line.startswith("data: "):
                                    if line.strip() == "data: [DONE]":
                                        break
                                    try:
                                        data = json_module.loads(line[6:])
                                        choices = data.get("choices", [])
                                        if choices:
                                            content = choices[0].get("delta", {}).get("content", "")
                                            if content:
                                                yield content
                                    except json_module.JSONDecodeError:
                                        continue
                        return

                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            if line.strip() == "data: [DONE]":
                                break
                            try:
                                data = json_module.loads(line[6:])
                                choices = data.get("choices", [])
                                if choices:
                                    content = choices[0].get("delta", {}).get("content", "")
                                    if content:
                                        yield content
                            except json_module.JSONDecodeError:
                                continue
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise Exception("GitHub Copilot 认证失败，请在设置中重新登录 GitHub")
                raise


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

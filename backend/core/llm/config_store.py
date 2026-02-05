"""
LLM 配置存储
支持持久化存储 LLM 配置
"""
import json
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum

from backend.config import DATA_DIR


class LLMProviderType(str, Enum):
    """LLM 服务商类型"""
    OPENAI_COMPATIBLE = "openai_compatible"  # OpenAI 兼容 API (DeepSeek, 通义千问等)
    GOOGLE_GEMINI = "google_gemini"          # Google AI Studio
    GITHUB_COPILOT = "github_copilot"        # GitHub Copilot


class LLMConfig(BaseModel):
    """LLM 配置"""
    provider: LLMProviderType = LLMProviderType.OPENAI_COMPATIBLE
    api_key: str = ""
    # 注意：OpenAI SDK 期望 base_url 包含 /v1
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    # Optional: image generation model (OpenAI-compatible /images/generations).
    # When empty, diagram generation falls back to local infographic rendering.
    image_model: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096

    # GitHub OAuth
    github_token: Optional[str] = None
    github_user: Optional[str] = None

    # Provider display name (for UI)
    provider_name: str = "DeepSeek"


# 预设的服务商配置
PROVIDER_PRESETS = {
    "deepseek": {
        "provider": LLMProviderType.OPENAI_COMPATIBLE,
        "provider_name": "DeepSeek",
        # OpenAI compatible endpoint root
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-coder"],
    },
    "openai": {
        "provider": LLMProviderType.OPENAI_COMPATIBLE,
        "provider_name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "zhipu": {
        "provider": LLMProviderType.OPENAI_COMPATIBLE,
        "provider_name": "智谱 AI",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "models": ["glm-4-plus", "glm-4-flash", "glm-4-air"],
    },
    "qwen": {
        "provider": LLMProviderType.OPENAI_COMPATIBLE,
        "provider_name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
    },
    "ollama": {
        "provider": LLMProviderType.OPENAI_COMPATIBLE,
        "provider_name": "Ollama (本地)",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2:7b",
        "models": ["qwen2:7b", "llama3:8b", "mistral:7b"],
        "no_api_key": True,
    },
    "google_gemini": {
        "provider": LLMProviderType.GOOGLE_GEMINI,
        "provider_name": "Google AI Studio",
        # Gemini API root (models endpoint is `${base_url}/models`)
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        # Default model
        "model": "gemini-3-flash-preview",
        # Curated list (from local docs); keep this list explicit to avoid relying on dynamic fetch.
        "models": [
            # Gemini 3 (preview)
            "gemini-3-flash-preview",
            "gemini-3-pro-preview",
            "gemini-3-pro-image-preview",

            # Gemini 2.5 Pro
            "gemini-2.5-pro",
            "gemini-2.5-pro-preview-03-25",
            "gemini-2.5-pro-preview-05-06",
            "gemini-2.5-pro-preview-06-05",

            # Gemini 2.5 Flash
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash-image",
            "gemini-2.5-flash-preview-05-20",
            "gemini-2.5-flash-preview-09-25",
            "gemini-2.5-flash-image-preview",

            # Gemini 2.0
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash-lite-001",
            "gemini-2.0-flash-preview-image-generation",
            "gemini-2.0-flash-lite-preview",
            "gemini-2.0-flash-lite-preview-02-05",
        ],
    },
    "github_copilot": {
        "provider": LLMProviderType.GITHUB_COPILOT,
        "provider_name": "GitHub Copilot",
        "base_url": "https://api.githubcopilot.com",
        "model": "gpt-4o",
        "models": [
            # OpenAI models
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "o1",
            "o1-mini",
            "o1-preview",
            "o3-mini",
            # Anthropic models
            "claude-3.5-sonnet",
            "claude-3.5-haiku",
            "claude-sonnet-4",
            # Google models
            "gemini-2.0-flash",
            "gemini-2.5-pro",
        ],
        "requires_oauth": True,
    },
    "antigravity": {
        "provider": LLMProviderType.OPENAI_COMPATIBLE,
        "provider_name": "antigravity",
        "base_url": "http://127.0.0.1:8045/v1",
        "model": "gemini-3-flash",
        "models": [],
    },
}


CONFIG_FILE = DATA_DIR / "llm_config.json"


def get_llm_config() -> LLMConfig:
    """获取 LLM 配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                config = LLMConfig(**data)
                # 轻量迁移：早期 DeepSeek 预设缺少 /v1 会导致 404
                if (
                    (config.provider_name or "").lower() == "deepseek"
                    and (config.base_url or "").rstrip("/") == "https://api.deepseek.com"
                ):
                    config.base_url = "https://api.deepseek.com/v1"
                    save_llm_config(config)
                return config
        except Exception:
            pass

    # 返回默认配置，尝试从环境变量读取
    import os
    return LLMConfig(
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
    )


def save_llm_config(config: LLMConfig) -> bool:
    """保存 LLM 配置"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config.model_dump(), f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save LLM config: {e}")
        return False


def get_provider_presets() -> dict:
    """获取预设服务商列表"""
    return PROVIDER_PRESETS


def has_llm_credentials(config: Optional[LLMConfig] = None) -> bool:
    """判断是否已配置可用的 LLM 凭据"""
    config = config or get_llm_config()
    if not config.model or not config.base_url:
        return False
    if config.provider == LLMProviderType.GITHUB_COPILOT:
        return bool(config.github_token)
    if config.provider == LLMProviderType.GOOGLE_GEMINI:
        return bool(config.api_key)
    if config.api_key:
        return True
    # Some local OpenAI-compatible providers (e.g. Ollama) may not require API keys.
    # For most gateways/proxies (including local ones), require an API key unless we can
    # confidently identify a no-key local provider by base_url/provider_name.
    base_url = (config.base_url or "").lower()
    provider_name = (config.provider_name or "").lower()
    is_local = ("localhost" in base_url) or ("127.0.0.1" in base_url)
    is_ollama = ("11434" in base_url) or ("ollama" in provider_name)
    return is_local and is_ollama

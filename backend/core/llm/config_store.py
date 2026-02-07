"""
LLM 配置存储
支持持久化存储 LLM 配置
"""
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from enum import Enum
import logging

from backend.config import DATA_DIR

logger = logging.getLogger(__name__)

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


CONFIG_FILE = DATA_DIR / "llm_config.json"
MODELS_FILE = DATA_DIR / "models.json"


def _load_presets_from_json() -> Dict[str, Any]:
    """从 models.json 加载预设，并转换为系统内部格式"""
    presets = {}

    # 1. 加载 JSON 配置
    if MODELS_FILE.exists():
        try:
            with open(MODELS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for provider in data.get("providers", []):
                pid = provider.get("id")
                name = provider.get("name")
                base_url = provider.get("base_url")
                models = provider.get("models", [])

                if not pid or not models:
                    continue

                # 映射 Provider Type
                provider_type = LLMProviderType.OPENAI_COMPATIBLE
                if pid == "google":
                    provider_type = LLMProviderType.GOOGLE_GEMINI

                # 保持模型对象结构，供前端筛选
                default_model = models[0]["id"] if models else ""

                presets[pid] = {
                    "provider": provider_type,
                    "provider_name": name,
                    "base_url": base_url,
                    "model": default_model,
                    "models": models,
                    "no_api_key": pid == "ollama", # 特殊处理 Ollama
                }
        except Exception as e:
            logger.error(f"Failed to load models.json: {e}")

    # 2. 注入 GitHub Copilot (应用特定逻辑，不在通用注册表中)
    presets["github_copilot"] = {
        "provider": LLMProviderType.GITHUB_COPILOT,
        "provider_name": "GitHub Copilot",
        "base_url": "https://api.githubcopilot.com",
        "model": "gpt-4o",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o", "type": "chat"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "type": "chat"},
            {"id": "o1", "name": "o1", "type": "chat"},
            {"id": "o1-mini", "name": "o1-mini", "type": "chat"},
            {"id": "claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "type": "chat"},
            {"id": "gemini-2.0-flash-preview-02-05", "name": "Gemini 2.0 Flash", "type": "chat"}
        ],
        "requires_oauth": True,
    }

    return presets


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
    return _load_presets_from_json()


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
    base_url = (config.base_url or "").lower()
    provider_name = (config.provider_name or "").lower()
    is_local = ("localhost" in base_url) or ("127.0.0.1" in base_url)
    is_ollama = ("11434" in base_url) or ("ollama" in provider_name)
    return is_local and is_ollama

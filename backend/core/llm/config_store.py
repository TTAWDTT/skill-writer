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
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
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
        "base_url": "https://api.deepseek.com",
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
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-1.5-flash",
        "models": ["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro"],
    },
    "github_copilot": {
        "provider": LLMProviderType.GITHUB_COPILOT,
        "provider_name": "GitHub Copilot",
        "base_url": "https://api.githubcopilot.com",
        "model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet", "o1-mini", "o1-preview"],
        "requires_oauth": True,
    },
}


CONFIG_FILE = DATA_DIR / "llm_config.json"


def get_llm_config() -> LLMConfig:
    """获取 LLM 配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return LLMConfig(**data)
        except Exception:
            pass

    # 返回默认配置，尝试从环境变量读取
    import os
    return LLMConfig(
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
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

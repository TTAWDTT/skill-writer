"""
Skill Writer 配置文件
使用环境变量管理敏感信息
"""
import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings


# 项目路径（在类外定义，避免 pydantic 验证问题）
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SKILLS_DIR = DATA_DIR / "skills"


class Settings(BaseSettings):
    """应用配置"""

    # 应用信息
    APP_NAME: str = "SkillWriter"
    APP_VERSION: str = "0.1.0"

    # API 配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174"]

    # LLM 配置
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    # OpenAI SDK 期望 base_url 包含 /v1
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_RETRIES: int = 3

    # 数据库配置
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/skill_writer.db")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

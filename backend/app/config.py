import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Agent Orchestrator"
    DEBUG: bool = True

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./agent_orchestrator.db"

    # AI API
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    DEFAULT_AI_PROVIDER: str = "deepseek"
    DEFAULT_AI_MODEL: str = "deepseek-chat"

    # GitHub
    GITHUB_TOKEN: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""

    # 执行引擎
    MAX_TOKENS_PER_TASK: int = 500_000
    TASK_TIMEOUT_SECONDS: int = 1800  # 30 分钟

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

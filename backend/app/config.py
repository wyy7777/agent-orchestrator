import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Agent Orchestrator"
    DEBUG: bool = False

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./agent_orchestrator.db"

    # AI API
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    DEFAULT_AI_PROVIDER: str = "deepseek"
    DEFAULT_AI_MODEL: str = "deepseek-chat"
    DEFAULT_MAX_TOKENS: int = 4096

    # GitHub
    GITHUB_TOKEN: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""

    # 执行引擎
    MAX_TOKENS_PER_TASK: int = 500_000
    TASK_TIMEOUT_SECONDS: int = 1800  # 30 分钟
    STEP_TIMEOUT_SECONDS: int = 300  # 5 分钟

    # API 安全
    API_KEY: str = ""  # 可选：客户端 API Key，留空则不验证
    CORS_ORIGINS: str = "*"  # 逗号分隔的允许来源

    # AI 调用
    AI_MAX_RETRIES: int = 3
    AI_TIMEOUT_SECONDS: int = 120

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


settings = Settings()

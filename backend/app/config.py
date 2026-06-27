import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Agent Orchestrator"
    APP_VERSION: str = "1.2.0"
    DEBUG: bool = False

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./agent_orchestrator.db"

    # Redis（缓存 / 任务队列）
    REDIS_URL: str = ""

    # AI API
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    DEFAULT_AI_PROVIDER: str = "deepseek"
    DEFAULT_AI_MODEL: str = "deepseek-chat"
    DEFAULT_MAX_TOKENS: int = 4096

    # Ollama（本地模型）
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_DEFAULT_MODEL: str = "qwen2.5-coder:7b"

    # GitHub
    GITHUB_TOKEN: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""

    # GitLab
    GITLAB_TOKEN: str = ""

    # Bitbucket
    BITBUCKET_TOKEN: str = ""

    # 执行引擎
    MAX_TOKENS_PER_TASK: int = 500_000
    TASK_TIMEOUT_SECONDS: int = 1800  # 30 分钟
    STEP_TIMEOUT_SECONDS: int = 300  # 5 分钟

    # API 安全
    API_KEY: str = ""  # 可选：客户端 API Key，留空则不验证
    CORS_ORIGINS: str = "*"  # 逗号分隔的允许来源

    # 速率限制
    RATE_LIMIT: int = 60  # 每窗口最大请求数
    RATE_WINDOW: int = 60  # 时间窗口（秒）

    # YAML 解析默认值
    DEFAULT_STEP_TIMEOUT: int = 300  # 步骤默认超时（秒）
    DEFAULT_MAX_ITERATIONS: int = 10  # 循环默认最大迭代次数

    # AI 调用
    AI_MAX_RETRIES: int = 3
    AI_TIMEOUT_SECONDS: int = 120

    # 通知
    SLACK_WEBHOOK_URL: str = ""
    DINGTALK_WEBHOOK_URL: str = ""
    WECHAT_WORK_WEBHOOK_URL: str = ""
    FEISHU_WEBHOOK_URL: str = ""
    NOTIFY_ON_TASK_COMPLETE: bool = True
    NOTIFY_ON_TASK_FAIL: bool = True
    NOTIFY_ON_APPROVAL_NEEDED: bool = True

    # JWT 认证
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 小时

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # SSO / OAuth2
    OAUTH2_ENABLED: bool = False
    OAUTH2_GOOGLE_CLIENT_ID: str = ""
    OAUTH2_GOOGLE_CLIENT_SECRET: str = ""
    OAUTH2_GITHUB_CLIENT_ID: str = ""
    OAUTH2_GITHUB_CLIENT_SECRET: str = ""
    OAUTH2_MICROSOFT_CLIENT_ID: str = ""
    OAUTH2_MICROSOFT_CLIENT_SECRET: str = ""
    OAUTH2_REDIRECT_BASE: str = "http://localhost:8000"

    # 数据安全
    DATA_RETENTION_DAYS: int = 0  # 0 = 不自动清理，>0 清理 N 天前的数据
    ENCRYPTION_KEY: str = ""  # AES-256 密钥，留空则自动生成
    ALLOWED_IPS: str = ""  # IP 白名单，逗号分隔的 CIDR，留空不限制

    model_config = {
        "env_file": os.environ.get("AGENT_ORCH_DOTENV", ".env"),
        "env_file_encoding": "utf-8",
    }

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


settings = Settings()

import enum
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(enum.StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    ERROR = "ERROR"


APP_ENV = os.getenv("YL_RAG_ENVIRONMENT", "dev")
ENV_FILE = f".env.{APP_ENV}"


class Settings(BaseSettings):
    app_name: str = "YL-RAG"
    environment: str = "dev"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    # 安全优化：默认不再内置 API Key，避免凭据硬编码泄露风险
    qdrant_api_key: str | None = None
    collection_name: str = "memory_palace"

    embedder_model: str = "BAAI/bge-base-zh-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    time_decay_lambda: float = 0.05
    model_cache_dir: str = "./cache/models"

    log_level: LogLevel = LogLevel.DEBUG

    # --- 运行参数 ---
    host: str = "127.0.0.1"
    port: int = 8000
    workers_count: int = 1
    reload: bool = True

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix="YL_RAG_",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# 调试信息只展示非敏感配置
if settings.log_level == LogLevel.DEBUG:
    print(f"Loaded config from: {ENV_FILE}")
    print(f"Qdrant Host: {settings.qdrant_host}:{settings.qdrant_port}")

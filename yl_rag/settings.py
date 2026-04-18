from __future__ import annotations

import enum
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(enum.StrEnum):
    """Application log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    ERROR = "ERROR"


APP_ENV = os.getenv("YL_RAG_ENVIRONMENT", "dev")
ENV_FILE = f".env.{APP_ENV}"


class Settings(BaseSettings):
    """Environment-driven project configuration."""

    app_name: str = "YL-RAG"
    environment: str = "dev"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = "112300"
    collection_name: str = "memory_palace"

    embedder_model: str = "BAAI/bge-base-zh-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    embed_batch_size: int = 32
    rerank_batch_size: int = 32
    time_decay_lambda: float = 0.05
    model_cache_dir: str = "./cache/models"

    log_level: LogLevel = LogLevel.DEBUG

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

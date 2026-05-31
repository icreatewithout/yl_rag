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
    qdrant_api_key: str | None = "112300"
    collection_name: str = "memory_palace"

    embedder_model: str = "BAAI/bge-base-zh-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    time_decay_lambda: float = 0.05
    model_cache_dir: str = "./cache/models"

    # --- 模型推理性能参数 ---
    # auto: 自动检测 CUDA；cuda: 强制 GPU（不可用时自动回退 CPU）；cpu: 强制 CPU
    inference_device: str = "auto"
    enable_batch_mode: bool = True
    embedding_batch_size: int = 32
    reranker_batch_size: int = 16
    cpu_threads: int = max(1, (os.cpu_count() or 2) - 1)

    log_level: LogLevel = LogLevel.DEBUG

    # --- 运行参数 ---
    host: str = "127.0.0.1"
    port: int = 8000
    # quantity of workers for uvicorn
    workers_count: int = 1
    # Enable uvicorn reloading
    reload: bool = True

    print(f".env.{os.getenv('APP_ENV', 'dev')}")

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix="YL_RAG_",
        env_file_encoding="utf-8",
        extra="ignore",  # 允许 .env 中存在类中没定义的变量
    )


settings = Settings()

# 仅在调试时打印
if settings.log_level == LogLevel.DEBUG:
    print(f" Loaded config from: {ENV_FILE}")
    print(f" Qdrant Host: {settings.qdrant_host}")

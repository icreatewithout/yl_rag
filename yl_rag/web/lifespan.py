from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from yl_rag.services.embedder import embedding_service


@asynccontextmanager
async def lifespan_setup(
    app: FastAPI,
) -> AsyncGenerator[None]:  # pragma: no cover
    """
    Actions to run on application startup.

    This function uses fastAPI app to store data
    in the state, such as db_engine.

    :param app: the fastAPI application.
    :return: function that actually performs actions.
    """
    # 启动时的操作
    print("--- SERVER STARTING ---")
    # 这里可以显式访问一下 embedding_service 确保它已加载
    _ = embedding_service.device
    print(f"--- MODELS READY ON {embedding_service.device} ---")
    yield
    # 关闭时的操作（如保存图谱）
    print("--- SERVER SHUTTING DOWN ---")

    app.middleware_stack = None
    app.middleware_stack = app.build_middleware_stack()

    yield

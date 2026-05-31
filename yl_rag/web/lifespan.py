from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from yl_rag.services.embedder import get_embedding_service
from yl_rag.settings import settings


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
    print("--- SERVER STARTING ---")
    if settings.environment != "pytest":
        embedding_service = get_embedding_service()
        print(f"--- MODELS READY ON {embedding_service.device} ---")
    yield
    print("--- SERVER SHUTTING DOWN ---")

    app.middleware_stack = None
    app.middleware_stack = app.build_middleware_stack()

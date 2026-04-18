from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from yl_rag.services.embedder import embedding_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan_setup(app: FastAPI) -> AsyncGenerator[None]:  # pragma: no cover
    """Run startup/shutdown actions for FastAPI app."""
    logger.info("Server starting")
    _ = embedding_service.device
    logger.info("Embedding service prepared on %s", embedding_service.device)
    yield
    logger.info("Server shutting down")
    app.middleware_stack = None
    app.middleware_stack = app.build_middleware_stack()

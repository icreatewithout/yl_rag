from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from yl_rag.core.models import MemoryInput, SearchQuery, SearchResult
from yl_rag.services.qdrant_db import qdrant_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/memory/add", tags=["Memory"])
def add_memory(data: MemoryInput) -> dict[str, str]:
    """Add one memory item to vector storage and graph storage."""
    try:
        qdrant_service.add_memory(data.text, data.id, data.tags, data.role)
        return {"status": "success", "message": f"Memory stored in {data.id}"}
    except Exception as err:
        logger.exception("Failed to add memory")
        raise HTTPException(status_code=500, detail=str(err)) from err


@router.post("/memory/search", response_model=list[SearchResult], tags=["Retrieval"])
def search(query: SearchQuery) -> list[dict[str, Any]]:
    """Search memories by semantic relevance and optional id filter."""
    try:
        return qdrant_service.search(query.text, query.id_filter, query.top_k)
    except Exception as err:
        logger.exception("Failed to search memory")
        raise HTTPException(status_code=500, detail=str(err)) from err

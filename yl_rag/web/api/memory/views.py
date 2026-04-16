from fastapi import APIRouter, HTTPException

from yl_rag.core.models import MemoryInput, SearchQuery, SearchResult
from yl_rag.services.qdrant_db import qdrant_service

router = APIRouter()


@router.post("/memory/add", tags=["Memory"])
def add_memory(data: MemoryInput):
    try:
        qdrant_service.add_memory(data.text, data.room, data.tags, data.shelf)
        return {"status": "success", "message": f"Memory stored in {data.room}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/search", response_model=list[SearchResult], tags=["Retrieval"])
def search(query: SearchQuery):
    try:
        return qdrant_service.search(query.text, query.room_filter, query.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

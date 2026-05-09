from fastapi.routing import APIRouter

from yl_rag.web.api import docs, echo, memory, monitoring, novel

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(docs.router)
api_router.include_router(docs.router)
api_router.include_router(memory.router)
api_router.include_router(novel.router)
api_router.include_router(echo.router, prefix="/echo", tags=["echo"])

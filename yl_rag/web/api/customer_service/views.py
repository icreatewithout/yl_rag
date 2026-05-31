from __future__ import annotations

from fastapi import APIRouter, HTTPException

from yl_rag.core.customer_service import (
    CustomerChatRequest,
    CustomerChatResponse,
    CustomerIngestRequest,
    CustomerIngestResponse,
)
from yl_rag.services.customer_service import customer_service_rag

router = APIRouter(prefix="/customer-service", tags=["CustomerService"])


@router.post("/ingest", response_model=CustomerIngestResponse)
def ingest_customer_service_docs(
    data: CustomerIngestRequest,
) -> CustomerIngestResponse:
    """Store canonical customer-service documents in the RAG library."""
    try:
        return customer_service_rag.ingest_documents(data.documents)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/chat", response_model=CustomerChatResponse)
def chat_with_customer_service(data: CustomerChatRequest) -> CustomerChatResponse:
    """Answer a user message through retrieval-augmented customer service."""
    try:
        return customer_service_rag.answer(
            message=data.message,
            tenant_id=data.tenant_id,
            session_id=data.session_id,
            top_k=data.top_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

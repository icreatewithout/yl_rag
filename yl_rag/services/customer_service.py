from __future__ import annotations

from yl_rag.core.customer_service import (
    CustomerChatResponse,
    CustomerIngestResponse,
    CustomerServiceDocument,
    CustomerSource,
)
from yl_rag.services.qdrant_db import get_qdrant_service


class CustomerServiceRAG:
    """Customer-service workflow built on the existing yl_rag vector store."""

    def ingest_documents(
        self,
        documents: list[CustomerServiceDocument],
    ) -> CustomerIngestResponse:
        """Store canonical customer-service documents in the RAG collection."""
        qdrant = get_qdrant_service()
        for document in documents:
            qdrant.add_memory(
                text=document.to_rag_text(),
                id=document.tenant_id,
                tags=document.to_memory_tags(),
                role="customer_service_document",
            )
        return CustomerIngestResponse(
            status="success",
            stored=len(documents),
            ids=[document.doc_id for document in documents],
        )

    def answer(
        self,
        message: str,
        tenant_id: str = "default",
        session_id: str | None = None,
        top_k: int = 5,
    ) -> CustomerChatResponse:
        """Retrieve relevant snippets and compose a grounded support answer."""
        qdrant = get_qdrant_service()
        results = qdrant.search(message, id_filter=tenant_id, top_k=top_k)
        sources = [
            CustomerSource(
                id=str(result["id"]),
                score=float(result["score"]),
                text=str(result.get("payload", {}).get("text", "")),
                payload=dict(result.get("payload", {})),
            )
            for result in results
        ]
        if not sources:
            return CustomerChatResponse(
                answer="抱歉, 我暂时没有在知识库中找到准确答案, 已为您转人工客服。",
                session_id=session_id,
                sources=[],
                fallback=True,
            )

        answer = self._compose_answer(message, sources)
        return CustomerChatResponse(
            answer=answer,
            session_id=session_id,
            sources=sources,
            fallback=False,
        )

    @staticmethod
    def _compose_answer(message: str, sources: list[CustomerSource]) -> str:
        """Create a deterministic answer from retrieved knowledge snippets."""
        snippets = []
        for index, source in enumerate(sources[:3], start=1):
            text = source.text.strip()
            if len(text) > 420:
                text = f"{text[:420]}..."
            snippets.append(f"{index}. {text}")
        joined_sources = "\n".join(snippets)
        return (
            f"我根据知识库为您查询到以下信息(问题: {message}):\n"
            f"{joined_sources}\n"
            "如果以上信息没有覆盖您的具体情况, 请补充订单号、商品型号或问题截图。"
        )


customer_service_rag = CustomerServiceRAG()

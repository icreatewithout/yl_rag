from pytest import MonkeyPatch

from yl_rag.core.customer_service import CustomerServiceDocument
from yl_rag.services.customer_service import CustomerServiceRAG


def test_customer_service_document_renders_stable_rag_text() -> None:
    """Customer-service documents render deterministic RAG text."""
    document = CustomerServiceDocument(
        doc_id="faq_return_001",
        tenant_id="store_1001",
        doc_type="faq",
        title="7天无理由退货规则",
        question="商品签收后多久可以申请无理由退货?",
        answer="签收次日起7天内可申请, 特殊商品除外。",
        keywords=["退货", "退货", "售后"],
        product_ids=["SKU-BOOK-001"],
        updated_at="2026-05-31T00:00:00+00:00",
    )

    text = document.to_rag_text()

    assert "[文档ID] faq_return_001" in text
    assert "[租户] store_1001" in text
    assert "[标准答案] 签收次日起7天内可申请, 特殊商品除外。" in text
    assert document.to_memory_tags() == [
        "store_1001",
        "zh-CN",
        "faq",
        "退货",
        "售后",
        "SKU-BOOK-001",
    ]


def test_customer_service_answer_fallback(monkeypatch: MonkeyPatch) -> None:
    """Customer service returns fallback text when retrieval is empty."""
    class EmptyQdrant:
        def search(self, query: str, id_filter: str, top_k: int) -> list:
            return []

    def get_empty_qdrant() -> EmptyQdrant:
        return EmptyQdrant()

    monkeypatch.setattr(
        "yl_rag.services.customer_service.get_qdrant_service",
        get_empty_qdrant,
    )

    response = CustomerServiceRAG().answer("退货规则?", tenant_id="store_1001")

    assert response.fallback is True
    assert response.sources == []

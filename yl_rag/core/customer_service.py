from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CustomerDocType(StrEnum):
    """Supported customer-service document categories."""

    faq = "faq"
    policy = "policy"
    product = "product"
    troubleshooting = "troubleshooting"
    workflow = "workflow"


class CustomerServiceDocument(BaseModel):
    """Canonical text format stored in the RAG knowledge base."""

    doc_id: str = Field(..., description="Stable business document id")
    tenant_id: str = Field(default="default", description="Tenant or shop id")
    locale: str = Field(default="zh-CN", description="Document language/locale")
    doc_type: CustomerDocType = Field(
        default=CustomerDocType.faq,
        description="Business category used for filtering and governance",
    )
    title: str = Field(..., max_length=120, description="Short searchable title")
    question: str | None = Field(
        default=None,
        max_length=200,
        description="FAQ question",
    )
    answer: str = Field(..., max_length=1200, description="Grounded answer text")
    keywords: list[str] = Field(default_factory=list, description="Synonyms/entities")
    product_ids: list[str] = Field(
        default_factory=list,
        description="Related SKU/SPU ids",
    )
    source_url: str | None = Field(default=None, description="Source-of-truth URL")
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO-8601 update time",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra payload")

    @field_validator("keywords", "product_ids")
    @classmethod
    def deduplicate_values(cls, values: list[str]) -> list[str]:
        """Keep input order while removing duplicate empty-normalized values."""
        seen: set[str] = set()
        normalized: list[str] = []
        for value in values:
            item = value.strip()
            if item and item not in seen:
                normalized.append(item)
                seen.add(item)
        return normalized

    def to_rag_text(self) -> str:
        """Render the document into a stable, chunk-friendly plain-text block."""
        fields = [
            f"[文档ID] {self.doc_id}",
            f"[租户] {self.tenant_id}",
            f"[语言] {self.locale}",
            f"[类型] {self.doc_type.value}",
            f"[标题] {self.title}",
        ]
        if self.question:
            fields.append(f"[用户问题] {self.question}")
        fields.append(f"[标准答案] {self.answer}")
        if self.keywords:
            fields.append(f"[关键词] {', '.join(self.keywords)}")
        if self.product_ids:
            fields.append(f"[商品ID] {', '.join(self.product_ids)}")
        if self.source_url:
            fields.append(f"[来源] {self.source_url}")
        fields.append(f"[更新时间] {self.updated_at}")
        return "\n".join(fields)

    def to_memory_tags(self) -> list[str]:
        """Return tags used by the existing vector-memory API."""
        return [
            self.tenant_id,
            self.locale,
            self.doc_type.value,
            *self.keywords,
            *self.product_ids,
        ]


class CustomerIngestRequest(BaseModel):
    """Request body for ingesting customer-service documents."""

    documents: list[CustomerServiceDocument] = Field(..., min_length=1, max_length=50)


class CustomerIngestResponse(BaseModel):
    """Response returned after documents are stored."""

    status: str
    stored: int
    ids: list[str]


class CustomerChatRequest(BaseModel):
    """REST chat request matching the Socket.IO message payload."""

    message: str = Field(..., min_length=1, max_length=500)
    tenant_id: str = Field(default="default")
    session_id: str | None = Field(default=None)
    top_k: int = Field(default=5, ge=1, le=10)


class CustomerSource(BaseModel):
    """Single retrieved source used to ground an answer."""

    id: str
    score: float
    text: str
    payload: dict[str, Any]


class CustomerChatResponse(BaseModel):
    """Answer payload emitted to REST clients and Socket.IO clients."""

    answer: str
    session_id: str | None
    sources: list[CustomerSource]
    fallback: bool = False

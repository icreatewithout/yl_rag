from __future__ import annotations

import hashlib
import logging
import math
import time
from typing import Any

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from yl_rag.services.embedder import embedding_service
from yl_rag.services.memory_graph import memory_graph
from yl_rag.settings import settings

logger = logging.getLogger(__name__)


class QdrantService:
    """Qdrant-backed memory retrieval service with local fallback."""

    def __init__(self) -> None:
        client_kwargs: dict[str, Any] = {
            "host": settings.qdrant_host,
            "port": settings.qdrant_port,
            "https": False,
            "check_compatibility": False,
        }
        if settings.qdrant_api_key:
            logger.warning("Ignoring qdrant_api_key because HTTPS is disabled.")

        self.client = QdrantClient(**client_kwargs)
        self.collection = settings.collection_name
        self.available = False
        self.local_store: dict[str, dict[str, Any]] = {}
        self._init_db()

    def _init_db(self) -> None:
        try:
            collections_response = self.client.get_collections()
            existing_collections = {c.name for c in collections_response.collections}
            if self.collection not in existing_collections:
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                    shard_number=2,
                )
                logger.info("Created collection %s", self.collection)
            self.available = True
        except Exception as err:
            logger.warning("Qdrant unavailable, switched to local mode: %s", err)
            self.available = False

    @staticmethod
    def _to_vector(vec: Any) -> list[float]:
        if isinstance(vec, np.ndarray):
            return vec.flatten().astype(float).tolist()
        return [float(v) for v in vec]

    def add_memory(
        self,
        text: str,
        id: str,
        tags: list[str],
        role: str | None,
    ) -> None:
        """Store memory into Qdrant or local fallback."""
        vector = self._to_vector(embedding_service.encode(text))
        doc_id = hashlib.sha256(f"{id}:{text}".encode()).hexdigest()
        payload = {
            "text": text,
            "id": id,
            "role": role or "user",
            "tags": tags,
            "created_at": time.time(),
        }
        memory_graph.add_memory(doc_id, tags, id)

        if not self.available:
            self.local_store[doc_id] = {"vector": vector, "payload": payload}
            return

        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=doc_id, vector=vector, payload=payload)],
        )

    def search(
        self,
        query: str,
        id_filter: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search memories by semantic similarity + rerank score."""
        if self.available:
            return self._search_qdrant(query=query, id_filter=id_filter, top_k=top_k)
        return self._search_local(query=query, id_filter=id_filter, top_k=top_k)

    def _search_qdrant(
        self,
        query: str,
        id_filter: str | None,
        top_k: int,
    ) -> list[dict[str, Any]]:
        query_vec = embedding_service.encode(query).flatten().tolist()
        query_filter = (
            Filter(must=[FieldCondition(key="id", match=MatchValue(value=id_filter))])
            if id_filter
            else None
        )
        response = self.client.query_points(
            collection_name=self.collection,
            query=query_vec,
            query_filter=query_filter,
            limit=20,
            with_payload=True,
        )

        now = time.time()
        candidates: list[dict[str, Any]] = []
        for hit in response.points:
            payload = hit.payload
            created_at = float(payload.get("created_at", now))
            seconds = max(0.0, now - created_at)
            decay = math.exp(-settings.time_decay_lambda * (seconds / 86400))
            candidates.append(
                {
                    "id": str(hit.id),
                    "payload": payload,
                    "score": float(hit.score) * decay,
                    "created_at": created_at,
                }
            )
        return self._rerank_and_sort(
            query=query,
            id_filter=id_filter,
            candidates=candidates,
            top_k=top_k,
        )

    def _search_local(
        self,
        query: str,
        id_filter: str | None,
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not self.local_store:
            return []

        query_vec = embedding_service.encode(query).flatten()
        now = time.time()
        candidates: list[dict[str, Any]] = []
        for doc_id, item in self.local_store.items():
            payload = item["payload"]
            if id_filter and payload.get("id") != id_filter:
                continue
            vector = np.asarray(item["vector"], dtype=np.float32)
            norm = np.linalg.norm(query_vec) * np.linalg.norm(vector)
            sim = float(np.dot(query_vec, vector) / norm) if norm else 0.0
            created_at = float(payload.get("created_at", now))
            seconds = max(0.0, now - created_at)
            decay = math.exp(-settings.time_decay_lambda * (seconds / 86400))
            candidates.append(
                {
                    "id": doc_id,
                    "payload": payload,
                    "score": sim * decay,
                    "created_at": created_at,
                }
            )
        return self._rerank_and_sort(
            query=query,
            id_filter=id_filter,
            candidates=candidates,
            top_k=top_k,
        )

    def _rerank_and_sort(
        self,
        query: str,
        id_filter: str | None,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        candidates.sort(key=lambda item: item["score"], reverse=True)
        top_candidates = candidates[:10]
        texts = [item["payload"].get("text", "") for item in top_candidates]
        rerank_scores = embedding_service.rerank(query, texts)

        for idx, rerank_score in enumerate(rerank_scores):
            candidate = top_candidates[idx]
            base = candidate["score"]
            graph_score = memory_graph.graph_score(
                doc_id=str(candidate["id"]),
                room=id_filter or candidate["payload"].get("id"),
                query=query,
            )
            candidate["score"] = (
                0.6 * base
                + 0.3 * float(rerank_score)
                + 0.1 * graph_score
            )

        top_candidates.sort(key=lambda item: item["score"], reverse=True)
        return top_candidates[:top_k]


qdrant_service = QdrantService()

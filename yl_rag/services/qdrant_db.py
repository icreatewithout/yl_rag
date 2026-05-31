import hashlib
import math
import time
from typing import Any

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from yl_rag.services.document_ingest import compute_sha256
from yl_rag.services.embedder import embedding_service
from yl_rag.services.memory_graph import memory_graph
from yl_rag.settings import settings


class QdrantService:
    def __init__(self):
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key,
            https=False,  # 强制关闭 HTTPS
            check_compatibility=False,  # 关闭版本检查
        )
        self.collection = settings.collection_name
        try:
            self._init_db()
        except UnexpectedResponse as e:
            # 💡 关键：捕获 502/401 等错误，允许应用先启动，而不是直接崩溃
            print(f"Warning: Cannot connect to Qdrant at startup (Reason: {e}). ")
            print("Please ensure Qdrant Docker is running and API Key is correct.")

    def _init_db(self):
        try:
            # 获取所有集合名称
            collections_response = self.client.get_collections()
            existing_collections = [c.name for c in collections_response.collections]
            if self.collection not in existing_collections:
                print(f"Collection '{self.collection}' not found. Creating...")

                # 创建集合
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(
                        size=768,  # BGE-Base 模型的向量维度是 768
                        distance=Distance.COSINE,  # 推荐使用余弦相似度
                    ),
                    # 可选：如果你需要更高的性能，可以配置分片数
                    shard_number=2,
                )
                print(f" Collection '{self.collection}' created successfully.")
            else:
                print(
                    f"Collection '{self.collection}' already exists. Skipping creation."
                )
        except Exception as e:
            print(f" Error during collection initialization: {e}")

    def add_memory(
        self,
        text: str,
        id: str,
        tags: list,
        role: str,
        source_name: str | None = None,
        document_id: str | None = None,
        chunk_index: int = 0,
        chunk_total: int = 1,
        document_sha256: str | None = None,
    ):
        vec = embedding_service.encode(text)
        # 如果 vector 的 shape 是 (1, 768)，需要降维成 (768,)
        # 如果使用 numpy，可以直接用 .flatten() 或 .tolist()
        if isinstance(vec, np.ndarray):
            # 确保它是一维数组：[0.1, 0.2, ...]
            processed_vector = vec.flatten().tolist()
        else:
            processed_vector = vec

        content_sha256 = compute_sha256(text)
        if self.has_sha256(content_sha256):
            return False

        doc_id = hashlib.md5(
            f"{document_id or ''}:{chunk_index}:{content_sha256}".encode(),
        ).hexdigest()
        payload = {
            "text": text,
            "id": id,
            "role": role,
            "tags": tags,
            "created_at": time.time(),
            "content_sha256": content_sha256,
            "document_sha256": document_sha256 or content_sha256,
            "source_name": source_name or "",
            "document_id": document_id or doc_id,
            "chunk_index": chunk_index,
            "chunk_total": chunk_total,
        }
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=doc_id, vector=processed_vector, payload=payload)],
        )
        memory_graph.add_memory(doc_id, tags, id)
        return True

    def has_sha256(self, content_sha256: str) -> bool:
        return self._has_payload_value("content_sha256", content_sha256)

    def has_document_sha256(self, document_sha256: str) -> bool:
        return self._has_payload_value("document_sha256", document_sha256)

    def _has_payload_value(self, key: str, value: str) -> bool:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key=key,
                    match=MatchValue(value=value),
                ),
            ],
        )
        points, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=query_filter,
            limit=1,
            with_payload=False,
        )
        return len(points) > 0

    def search(
        self,
        query: str,
        id_filter: str = None,
        top_k: int = 5,
        context_window: int = 1,
    ):
        # 1. 粗排 (召回候选集)
        query_vec = embedding_service.encode(query).flatten().tolist()
        filt = self._payload_filter(id_filter=id_filter)

        # 如果你的版本依然报 query_points 找不到，请确保 pip install --upgrade qdrant-client
        response = self.client.query_points(
            collection_name=self.collection,
            query=query_vec,  # 传入向量
            query_filter=filt,  # 过滤器
            limit=max(20, top_k * 4),  # 粗排召回数量
            with_payload=True,
        )

        hits = response.points
        if not hits:
            return []

        # 2. 时间衰减计算
        now = time.time()
        candidates = []
        for hit in hits:
            t_created = hit.payload.get("created_at", now)
            time_delta_seconds = max(0, now - t_created)
            decay = math.exp(
                -settings.time_decay_lambda * (time_delta_seconds / 86400),
            )
            score = max(0.0, float(hit.score)) * decay
            candidates.append({"hit": hit, "decay_score": score})

        candidates.sort(key=lambda x: x["decay_score"], reverse=True)
        top_candidates = candidates[: max(10, top_k * 2)]

        # 3. 精排 (Reranker)
        texts = [c["hit"].payload["text"] for c in top_candidates]
        rr_scores = embedding_service.rerank(query, texts)

        ranked = []
        for i, score in enumerate(rr_scores):
            ranked.append(
                {
                    "hit": top_candidates[i]["hit"],
                    "score": float(score),
                    "vector_score": float(top_candidates[i]["hit"].score),
                },
            )
        ranked.sort(key=lambda x: x["score"], reverse=True)

        # 4. 临近块合并：命中块前后各取 context_window 个块，按 chunk_index 顺序拼回上下文
        results: list[dict[str, Any]] = []
        seen_ranges: set[tuple[str, int, int]] = set()
        for item in ranked:
            hit = item["hit"]
            merged_payload = self._merge_neighbor_chunks(
                hit.payload,
                id_filter=id_filter,
                context_window=context_window,
            )
            document_id = str(merged_payload.get("document_id", hit.id))
            chunk_range = merged_payload.get("merged_chunk_range", [])
            start = (
                int(chunk_range[0])
                if chunk_range
                else int(merged_payload.get("chunk_index", 0))
            )
            end = int(chunk_range[1]) if len(chunk_range) > 1 else start
            range_key = (document_id, start, end)
            if range_key in seen_ranges:
                continue
            seen_ranges.add(range_key)

            results.append(
                {
                    "id": hit.id,
                    "payload": merged_payload,
                    "score": item["score"],
                    "created_at": hit.payload.get("created_at", 0.0),
                },
            )
            if len(results) >= top_k:
                break

        return results

    def _payload_filter(
        self,
        id_filter: str | None = None,
        document_id: str | None = None,
        chunk_index: int | None = None,
    ) -> Filter | None:
        conditions = []
        if id_filter:
            conditions.append(
                FieldCondition(key="id", match=MatchValue(value=id_filter)),
            )
        if document_id:
            conditions.append(
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
            )
        if chunk_index is not None:
            conditions.append(
                FieldCondition(key="chunk_index", match=MatchValue(value=chunk_index)),
            )
        return Filter(must=conditions) if conditions else None

    def _merge_neighbor_chunks(
        self,
        payload: dict,
        id_filter: str | None,
        context_window: int,
    ) -> dict:
        document_id = payload.get("document_id")
        chunk_index = payload.get("chunk_index")
        chunk_total = payload.get("chunk_total")
        if document_id is None or chunk_index is None:
            return payload

        safe_window = min(max(0, context_window), 5)
        current_idx = int(chunk_index)
        total = int(chunk_total or current_idx + 1)
        start_idx = max(0, current_idx - safe_window)
        end_idx = min(total - 1, current_idx + safe_window)

        neighbor_payloads: list[dict] = []
        for idx in range(start_idx, end_idx + 1):
            if idx == current_idx:
                neighbor_payloads.append(payload)
                continue
            neighbor = self._get_document_chunk(str(document_id), idx, id_filter)
            if neighbor:
                neighbor_payloads.append(neighbor)

        neighbor_payloads.sort(key=lambda item: int(item.get("chunk_index", 0)))
        if not neighbor_payloads:
            return payload

        merged_text = self._merge_texts([p.get("text", "") for p in neighbor_payloads])
        merged_payload = dict(payload)
        merged_payload["matched_text"] = payload.get("text", "")
        merged_payload["text"] = merged_text
        merged_payload["merged_chunk_range"] = [
            int(neighbor_payloads[0].get("chunk_index", current_idx)),
            int(neighbor_payloads[-1].get("chunk_index", current_idx)),
        ]
        merged_payload["merged_chunk_count"] = len(neighbor_payloads)
        return merged_payload

    def _get_document_chunk(
        self,
        document_id: str,
        chunk_index: int,
        id_filter: str | None,
    ) -> dict | None:
        points, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=self._payload_filter(
                id_filter=id_filter,
                document_id=document_id,
                chunk_index=chunk_index,
            ),
            limit=1,
            with_payload=True,
        )
        if not points:
            return None
        return points[0].payload

    def _merge_texts(self, texts: list[str]) -> str:
        merged = ""
        for text in texts:
            clean_text = text.strip()
            if not clean_text:
                continue
            if not merged:
                merged = clean_text
                continue
            overlap = self._find_overlap(merged, clean_text)
            if overlap > 0:
                merged = f"{merged}{clean_text[overlap:]}"
            else:
                merged = f"{merged}\n{clean_text}"
        return merged

    def _find_overlap(self, left: str, right: str, max_overlap: int = 300) -> int:
        max_len = min(len(left), len(right), max_overlap)
        for size in range(max_len, 0, -1):
            if left[-size:] == right[:size]:
                return size
        return 0


qdrant_service = QdrantService()

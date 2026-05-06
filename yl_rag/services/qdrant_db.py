import hashlib
import logging
import math
import time

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

from yl_rag.services.embedder import embedding_service
from yl_rag.services.memory_graph import memory_graph
from yl_rag.settings import settings

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(self):
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key,
            # 开发环境默认 HTTP，生产环境请在网关层启用 TLS
            https=False,
            check_compatibility=False,
        )
        self.collection = settings.collection_name
        try:
            self._init_db()
        except UnexpectedResponse as exc:
            # 启动容错：连接失败时不中断服务进程，避免整个 API 不可用
            logger.warning(
                "Cannot connect to Qdrant during startup: %s. "
                "Please verify service status and credentials.",
                exc,
            )

    def _init_db(self):
        collections_response = self.client.get_collections()
        existing_collections = [c.name for c in collections_response.collections]
        if self.collection in existing_collections:
            logger.info("Collection '%s' already exists.", self.collection)
            return

        logger.info("Collection '%s' not found, creating...", self.collection)
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            shard_number=2,
        )
        logger.info("Collection '%s' created successfully.", self.collection)

    def add_memory(self, text: str, id: str, tags: list, role: str):
        vec = embedding_service.encode(text)
        # 向量标准化为一维 list，确保可被 qdrant-client 序列化
        processed_vector = vec.flatten().tolist() if isinstance(vec, np.ndarray) else vec

        # 使用 sha256 替代 md5，降低碰撞风险
        doc_id = hashlib.sha256(text.encode("utf-8")).hexdigest()
        payload = {
            "text": text,
            "id": id,
            "role": role,
            "tags": tags,
            "created_at": time.time(),
        }
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=doc_id, vector=processed_vector, payload=payload)],
        )
        memory_graph.add_memory(doc_id, tags, id)

    def search(self, query: str, id_filter: str = None, top_k: int = 5):
        query_vec = embedding_service.encode(query).flatten().tolist()
        filt = (
            Filter(must=[FieldCondition(key="id", match=MatchValue(value=id_filter))])
            if id_filter
            else None
        )

        response = self.client.query_points(
            collection_name=self.collection,
            query=query_vec,
            query_filter=filt,
            limit=20,
            with_payload=True,
        )

        hits = response.points
        if not hits:
            return []

        now = time.time()
        candidates = []
        for hit in hits:
            t_created = hit.payload.get("created_at", now)
            time_delta_seconds = max(0, now - t_created)
            decay = math.exp(-settings.time_decay_lambda * (time_delta_seconds / 86400))
            # 修复异常：避免 int 截断导致大多数分数变成 0，影响排序质量
            score = max(0.0, float(hit.score)) * decay
            candidates.append({"hit": hit, "decay_score": score})

        candidates.sort(key=lambda x: x["decay_score"], reverse=True)
        top_10 = candidates[:10]

        texts = [c["hit"].payload["text"] for c in top_10]
        rr_scores = embedding_service.rerank(query, texts)

        results = []
        for i, score in enumerate(rr_scores):
            h = top_10[i]["hit"]
            results.append(
                {
                    "id": h.id,
                    "payload": h.payload,
                    # 综合时间衰减 + reranker，结果更稳定
                    "score": float(score) * top_10[i]["decay_score"],
                    "created_at": h.payload.get("created_at", 0.0),
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


qdrant_service = QdrantService()

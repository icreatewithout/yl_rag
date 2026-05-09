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
            # 保留原思路：开发环境默认 HTTP（生产建议网关层启用 TLS）
            https=False,
            # 保留原思路：关闭版本检查，避免因版本探测阻塞启动
            check_compatibility=False,
        )
        self.collection = settings.collection_name
        try:
            self._init_db()
        except UnexpectedResponse as exc:
            # 💡 保留原注释语义：捕获 502/401 等错误，允许应用先启动，而不是直接崩溃
            logger.warning(
                "Cannot connect to Qdrant during startup: %s. "
                "Please verify service status and credentials.",
                exc,
            )

    def _init_db(self):
        # 获取所有集合名称
        collections_response = self.client.get_collections()
        existing_collections = [c.name for c in collections_response.collections]
        if self.collection in existing_collections:
            logger.info("Collection '%s' already exists. Skipping creation.", self.collection)
            return

        logger.info("Collection '%s' not found. Creating...", self.collection)
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(
                # 保留原注释：BGE-Base 模型向量维度为 768
                size=768,
                # 保留原注释：推荐使用余弦相似度
                distance=Distance.COSINE,
            ),
            # 保留原注释：可通过分片数优化性能
            shard_number=2,
        )
        logger.info("Collection '%s' created successfully.", self.collection)


    def exists_memory(self, text: str, id_filter: str | None = None) -> bool:
        """检查相同文本是否已存在，避免重复入库。"""
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        must_conditions = [FieldCondition(key="text_hash", match=MatchValue(value=text_hash))]
        if id_filter:
            must_conditions.append(FieldCondition(key="id", match=MatchValue(value=id_filter)))

        records, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=Filter(must=must_conditions),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        return len(records) > 0

    def add_memory(self, text: str, id: str, tags: list, role: str):
        if self.exists_memory(text=text, id_filter=id):
            logger.info("Duplicate memory detected for id=%s, skip insert.", id)
            return

        vec = embedding_service.encode(text)
        # 保留原注释：若 shape 是 (1, 768)，需要降维成 (768,)
        processed_vector = vec.flatten().tolist() if isinstance(vec, np.ndarray) else vec

        # 安全增强：使用 sha256 替代 md5，降低碰撞风险
        doc_id = hashlib.sha256(text.encode("utf-8")).hexdigest()
        payload = {
            "text": text,
            "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
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
        # 1. 粗排（召回候选集）
        query_vec = embedding_service.encode(query).flatten().tolist()
        filt = (
            Filter(must=[FieldCondition(key="id", match=MatchValue(value=id_filter))])
            if id_filter
            else None
        )

        # 保留原注释语义：若 query_points 不存在，需升级 qdrant-client
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

        # 2. 时间衰减计算
        now = time.time()
        candidates = []
        for hit in hits:
            t_created = hit.payload.get("created_at", now)
            time_delta_seconds = max(0, now - t_created)
            decay = math.exp(-settings.time_decay_lambda * (time_delta_seconds / 86400))
            # 修复异常：避免 int 截断导致分数异常归零
            score = max(0.0, float(hit.score)) * decay
            candidates.append({"hit": hit, "decay_score": score})

        candidates.sort(key=lambda x: x["decay_score"], reverse=True)
        top_10 = candidates[:10]

        # 3. 精排（Reranker）
        texts = [c["hit"].payload["text"] for c in top_10]
        rr_scores = embedding_service.rerank(query, texts)

        # 4. 封装输出
        results = []
        for i, score in enumerate(rr_scores):
            h = top_10[i]["hit"]
            results.append(
                {
                    "id": h.id,
                    "payload": h.payload,
                    # 综合时间衰减 + reranker，让时效与语义同时生效
                    "score": float(score) * top_10[i]["decay_score"],
                    "created_at": h.payload.get("created_at", 0.0),
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


qdrant_service = QdrantService()

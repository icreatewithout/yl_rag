import hashlib
import math
import time

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
            print(f"⚠️ Warning: Cannot connect to Qdrant at startup (Reason: {e}). ")
            print("Please ensure Qdrant Docker is running and API Key is correct.")

    def _init_db(self):
        try:
            # 获取所有集合名称
            collections_response = self.client.get_collections()
            existing_collections = [c.name for c in collections_response.collections]
            if self.collection not in existing_collections:
                print(f"📡 Collection '{self.collection}' not found. Creating...")

                # 创建集合
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(
                        size=768,  # BGE-Base 模型的向量维度是 768
                        distance=Distance.COSINE,  # 推荐使用余弦相似度
                    ),
                    # 可选：如果你需要更高的性能，可以配置分片数
                    # shard_number=2
                )
                print(f"✅ Collection '{self.collection}' created successfully.")
            else:
                print(
                    f"ℹ️ Collection '{self.collection}' already exists. Skipping creation."
                )
        except Exception as e:
            print(f"❌ Error during collection initialization: {e}")

    def add_memory(self, text: str, id: str, tags: list, role: str):
        vec = embedding_service.encode(text).tolist()
        doc_id = hashlib.md5(text.encode()).hexdigest()
        payload = {
            "text": text,
            "id": id,
            "role": role,
            "tags": tags,
            "created_at": time.time(),
        }
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=doc_id, vector=vec, payload=payload)],
        )
        memory_graph.add_memory(doc_id, tags, id)

    def search(self, query: str, id_filter: str = None, top_k: int = 5):
        # 1. 粗排 (召回候选集)
        query_vec = embedding_service.encode(query).tolist()
        filt = (
            Filter(must=[FieldCondition(key="id", match=MatchValue(value=id_filter))])
            if id_filter
            else None
        )

        # 如果你的版本依然报 query_points 找不到，请确保 pip install --upgrade qdrant-client
        response = self.client.query_points(
            collection_name=self.collection,
            query=query_vec,  # 传入向量
            query_filter=filt,  # 过滤器
            limit=20,  # 粗排召回数量
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
            # 注意：query_points 返回的 score 在 hit.score 中
            score = max(0, int(hit.score)) * decay
            candidates.append({"hit": hit, "decay_score": score})

        candidates.sort(key=lambda x: x["decay_score"], reverse=True)
        top_10 = candidates[:10]

        # 3. 精排 (Reranker)
        texts = [c["hit"].payload["text"] for c in top_10]
        rr_scores = embedding_service.rerank(query, texts)

        print(top_10)

        # 4. 封装输出
        results = []
        for i, score in enumerate(rr_scores):
            h = top_10[i]["hit"]
            print(h)
            results.append(
                {
                    "id": h.id,
                    "payload": h.payload,
                    "score": float(h.score),
                    "created_at": h.payload.get("created_at", 0.0),
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


qdrant_service = QdrantService()

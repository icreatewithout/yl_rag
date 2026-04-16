import logging
import os  # <--- 新增导入

import torch
from FlagEmbedding import FlagModel, FlagReranker

from yl_rag.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # 👇 确保模型存储目录存在
        os.makedirs(settings.model_cache_dir, exist_ok=True)

        # 启动时立即加载模型
        logger.info("🚀 Initializing AI Models (this may take a while on first run)...")
        self.embedder = self._safe_load(FlagModel, settings.embedder_model)
        self.reranker = self._safe_load(FlagReranker, settings.reranker_model)
        logger.info("✅ AI Models loaded successfully.")

    def _safe_load(self, model_class, name):
        try:
            logger.info(
                f"Loading {name} on {self.device} (Cache: {settings.model_cache_dir})..."
            )
            return model_class(
                name,
                use_onnx=True,
                devices=self.device,
                cache_dir=settings.model_cache_dir,  # <--- 👇 重点：将缓存路径传给底层模型
            )
        except Exception as e:
            if self.device == "cuda":
                logger.warning(f"CUDA Load failed: {e}. Falling back to CPU...")
                return model_class(
                    name,
                    use_onnx=True,
                    devices="cpu",
                    cache_dir=settings.model_cache_dir,  # <--- 👇 这里也要加上
                )
            raise e

    def encode(self, text: str):
        return self.embedder.encode(text)

    def rerank(self, query: str, texts: list):
        if not texts:
            return []
        pairs = [[query, t] for t in texts]
        return self.reranker.compute_score(pairs)


embedding_service = EmbeddingService()

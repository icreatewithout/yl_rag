import logging
import os  # <--- 新增导入

import numpy as np
import torch
from FlagEmbedding import FlagModel, FlagReranker

from yl_rag.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        # 1. 确定设备
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        os.makedirs(settings.model_cache_dir, exist_ok=True)

        logger.info(f"🚀 Initializing AI Models on {self.device.upper()}...")

        # 2. 优化加载参数
        # use_fp16: GPU 下开启半精度，显存减半，速度翻倍
        self.use_fp16 = self.device == "cuda"

        # 加载 Embedder
        self.embedder = self._safe_load(
            FlagModel, settings.embedder_model, is_reranker=False
        )

        # 加载 Reranker
        self.reranker = self._safe_load(
            FlagReranker, settings.reranker_model, is_reranker=True
        )

        logger.info("✅ AI Models loaded successfully.")

    def _safe_load(self, model_class, name, is_reranker=False):
        # 针对 BGE 模型的参数微调
        # 注意：FlagEmbedding 的推理后端在设置了 use_onnx=True 时，
        # 需要确保你已经安装了 onnxruntime-gpu (CUDA) 或 onnxruntime (CPU)
        common_kwargs = {
            "model_name_or_path": name,
            "cache_dir": settings.model_cache_dir,
            "use_fp16": self.use_fp16,
        }

        try:
            # Reranker 和 FlagModel 的参数名略有不同
            if is_reranker:
                return model_class(**common_kwargs)
            # FlagModel 额外支持 query 指令优化
            return model_class(**common_kwargs, devices=self.device)
        except Exception as e:
            logger.warning(f"Failed to load {name} on {self.device}: {e}")
            if self.device == "cuda":
                logger.info("🔄 Falling back to CPU...")
                common_kwargs["use_fp16"] = False
                if is_reranker:
                    return model_class(**common_kwargs)
                return model_class(**common_kwargs, devices="cpu")
            raise e

    def encode(self, texts: str | list[str]) -> np.ndarray:
        """
        优化：支持批量编码，显著提升吞吐量
        """
        # 自动处理单条文本
        input_texts = [texts] if isinstance(texts, str) else texts

        # encode 内部会自动处理 batching
        return self.embedder.encode(input_texts, batch_size=32, convert_to_numpy=True)

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        """
        优化：加入空列表判断与类型保护
        """
        if not texts:
            return []

        pairs = [[query, t] for t in texts]
        # compute_score 在 BGE 里面默认返回 List[float]
        scores = self.reranker.compute_score(pairs, batch_size=32)

        # 确保返回的是 Python 原生 float 列表，方便 JSON 序列化
        return [float(s) for s in scores]


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Return a lazily initialized embedding service."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import numpy as np
import torch
from FlagEmbedding import FlagModel, FlagReranker

from yl_rag.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding + rerank service with lazy init and offline fallback."""

    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        Path(settings.model_cache_dir).mkdir(parents=True, exist_ok=True)
        self.use_fp16 = self.device == "cuda"
        self.embedder: Any | None = None
        self.reranker: Any | None = None
        self.ready = False

    def _safe_load(self, model_class: Any, name: str, *, is_reranker: bool) -> Any:
        common_kwargs = {
            "model_name_or_path": name,
            "cache_dir": settings.model_cache_dir,
            "use_fp16": self.use_fp16,
        }
        try:
            if is_reranker:
                return model_class(**common_kwargs)
            return model_class(**common_kwargs, devices=self.device)
        except Exception as err:
            logger.warning("Model load failed for %s on %s: %s", name, self.device, err)
            if self.device != "cuda":
                raise
            logger.info("Falling back to CPU for model %s", name)
            common_kwargs["use_fp16"] = False
            if is_reranker:
                return model_class(**common_kwargs)
            return model_class(**common_kwargs, devices="cpu")

    def _ensure_models(self) -> None:
        if self.ready:
            return
        try:
            self.embedder = self._safe_load(
                FlagModel,
                settings.embedder_model,
                is_reranker=False,
            )
            self.reranker = self._safe_load(
                FlagReranker,
                settings.reranker_model,
                is_reranker=True,
            )
            self.ready = True
            logger.info("Embedding models are ready on %s", self.device)
        except Exception as err:
            logger.warning("Using offline fallback embedder due to init error: %s", err)
            self.ready = False

    @staticmethod
    def _hash_embedding(text: str, *, dim: int = 768) -> np.ndarray:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], byteorder="big", signed=False)
        rng = np.random.default_rng(seed)
        vector = rng.standard_normal(dim)
        norm = np.linalg.norm(vector)
        return (vector / norm) if norm else vector

    def encode(self, texts: str | list[str]) -> np.ndarray:
        """Encode text(s) into dense vectors."""
        input_texts = [texts] if isinstance(texts, str) else texts
        self._ensure_models()
        if self.ready and self.embedder is not None:
            return self.embedder.encode(
                input_texts,
                batch_size=settings.embed_batch_size,
                convert_to_numpy=True,
            )
        vectors = [self._hash_embedding(text) for text in input_texts]
        return np.asarray(vectors, dtype=np.float32)

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        """Rerank candidate texts for one query."""
        if not texts:
            return []
        self._ensure_models()
        if self.ready and self.reranker is not None:
            pairs = [[query, text] for text in texts]
            scores = self.reranker.compute_score(
                pairs,
                batch_size=settings.rerank_batch_size,
            )
            return [float(score) for score in scores]

        query_terms = set(query.lower().split())
        scores: list[float] = []
        for text in texts:
            text_terms = set(text.lower().split())
            union = len(query_terms | text_terms) or 1
            overlap = len(query_terms & text_terms)
            scores.append(overlap / union)
        return scores


embedding_service = EmbeddingService()

import logging
import os
import threading
from collections.abc import Callable
from inspect import Parameter, signature
from typing import Any

import numpy as np
import torch
from FlagEmbedding import FlagModel, FlagReranker

from yl_rag.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


TOKENIZER_FAST_PAD_WARNING = (
    "You're using a BertTokenizerFast tokenizer. Please note that with a fast "
    "tokenizer, using the `__call__` method is faster than using a method to "
    "encode the text followed by a call to the `pad` method"
)


class TokenizerFastPadWarningFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return TOKENIZER_FAST_PAD_WARNING not in record.getMessage()


_TOKENIZER_WARNING_FILTER_INSTALLED = False


def _install_tokenizer_warning_filter() -> None:
    global _TOKENIZER_WARNING_FILTER_INSTALLED
    if _TOKENIZER_WARNING_FILTER_INSTALLED:
        return
    warning_filter = TokenizerFastPadWarningFilter()
    logging.getLogger("transformers").addFilter(warning_filter)
    logging.getLogger("transformers.tokenization_utils_base").addFilter(
        warning_filter,
    )
    _TOKENIZER_WARNING_FILTER_INSTALLED = True


def _call_with_supported_kwargs(
    method: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    try:
        method_signature = signature(method)
    except (TypeError, ValueError):
        return method(*args, **kwargs)
    parameters = method_signature.parameters
    if any(p.kind == Parameter.VAR_KEYWORD for p in parameters.values()):
        return method(*args, **kwargs)
    supported_kwargs = {
        key: value for key, value in kwargs.items() if key in parameters
    }
    return method(*args, **supported_kwargs)


class EmbeddingService:
    _instance: "EmbeddingService | None" = None
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        with self._init_lock:
            if self._initialized:
                return
            self._initialize_once()
            self._initialized = True

    def _initialize_once(self) -> None:
        _install_tokenizer_warning_filter()
        self._configure_cpu_threads()
        self.device = self._select_device()
        os.makedirs(settings.model_cache_dir, exist_ok=True)
        if not settings.inference_show_progress:
            os.environ.setdefault("TQDM_DISABLE", "1")

        logger.info(
            "🚀 Initializing AI Models on %s (batch_mode=%s, embed_batch=%s, rerank_batch=%s)...",
            self.device.upper(),
            settings.enable_batch_mode,
            self.embedding_batch_size,
            self.reranker_batch_size,
        )

        # use_fp16: GPU 下开启半精度，显存减半，速度更快；CPU 保持 fp32 兼容性。
        self.use_fp16 = self.device == "cuda"

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

        logger.info("✅ AI Models loaded successfully.")

    @property
    def embedding_batch_size(self) -> int:
        if not settings.enable_batch_mode:
            return 1
        return max(1, settings.embedding_batch_size)

    @property
    def reranker_batch_size(self) -> int:
        if not settings.enable_batch_mode:
            return 1
        return max(1, settings.reranker_batch_size)

    def _configure_cpu_threads(self) -> None:
        cpu_threads = max(1, settings.cpu_threads)
        torch.set_num_threads(cpu_threads)
        torch.set_num_interop_threads(max(1, min(4, cpu_threads)))
        logger.info("🧵 CPU torch threads configured: %s", cpu_threads)

    def _select_device(self) -> str:
        requested_device = settings.inference_device.lower()
        cuda_available = torch.cuda.is_available()
        if requested_device == "cpu":
            logger.info("CPU inference forced by YL_RAG_INFERENCE_DEVICE=cpu")
            return "cpu"
        if requested_device in {"auto", "cuda"} and cuda_available:
            gpu_name = torch.cuda.get_device_name(0)
            total_vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info("✅ CUDA detected: %s (%.1f GB VRAM)", gpu_name, total_vram_gb)
            if total_vram_gb <= 6.5:
                logger.info(
                    "🎛️ 6GB-class GPU detected; fp16 + configured batch sizes "
                    "will be used.",
                )
            return "cuda"
        if requested_device == "cuda" and not cuda_available:
            logger.warning("CUDA was requested but is unavailable; falling back to CPU.")
        return "cpu"

    def _safe_load(self, model_class, name, is_reranker=False):
        common_kwargs = {
            "model_name_or_path": name,
            "cache_dir": settings.model_cache_dir,
            "use_fp16": self.use_fp16,
        }

        try:
            if is_reranker:
                return model_class(**common_kwargs)
            return model_class(**common_kwargs, devices=self.device)
        except Exception as e:
            logger.warning("Failed to load %s on %s: %s", name, self.device, e)
            if self.device == "cuda":
                logger.info("🔄 Falling back to CPU...")
                self.device = "cpu"
                self.use_fp16 = False
                common_kwargs["use_fp16"] = False
                if is_reranker:
                    return model_class(**common_kwargs)
                return model_class(**common_kwargs, devices="cpu")
            raise e

    def encode(self, texts: str | list[str]) -> np.ndarray:
        """始终通过批量入口编码，避免逐条 encode/pad 带来的 fast tokenizer 警告。"""
        input_texts = [texts] if isinstance(texts, str) else texts
        return _call_with_supported_kwargs(
            self.embedder.encode,
            input_texts,
            batch_size=self.embedding_batch_size,
            convert_to_numpy=True,
            show_progress_bar=settings.inference_show_progress,
        )

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        """批量 rerank，空列表直接返回。"""
        if not texts:
            return []

        pairs = [[query, t] for t in texts]
        scores = _call_with_supported_kwargs(
            self.reranker.compute_score,
            pairs,
            batch_size=self.reranker_batch_size,
            show_progress_bar=settings.inference_show_progress,
        )
        return [float(s) for s in scores]


embedding_service = EmbeddingService()

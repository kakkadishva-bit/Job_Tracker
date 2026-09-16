"""
services/rag/embeddings.py
Embedding generation and caching.
"""
import os

# sentence-transformers imports `transformers`, which probes for TensorFlow. In
# environments where TensorFlow is installed but broken (e.g. a protobuf/ABI
# mismatch) that probe raises ImportError, which used to be swallowed here and
# silently degraded RAG to zero-vector embeddings => 0 retrieval hits. Disabling
# the TF/Flax backends keeps the embedding import pure PyTorch and reliable.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
# Keep model downloads non-interactive and offline-friendly (cached after the
# first run); no interactive auth prompt can ever block a web request.
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import json
import hashlib
import logging
from typing import List, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


def get_sentence_transformer_model():
    """Import lazily to allow fallback. Returns None (logged) on any failure."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer
    except Exception as e:  # pragma: no cover - environment dependent
        logger.error("sentence-transformers is unavailable (%s: %s); RAG embeddings "
                     "cannot be generated", type(e).__name__, e)
        return None


class EmbeddingCache:
    """Simple file-based cache for embeddings."""

    def __init__(self, cache_dir: str = ".cache/rag"):
        self._cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_path(self, text: str) -> str:
        h = hashlib.md5(text.encode()).hexdigest()
        return os.path.join(self._cache_dir, f"{h}.json")

    def get(self, text: str) -> Optional[List[float]]:
        if not self._cache_dir:
            return None
        path = self._get_cache_path(text)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def set(self, text: str, embedding: List[float]):
        if not self._cache_dir:
            return
        path = self._get_cache_path(text)
        try:
            with open(path, "w") as f:
                json.dump(embedding, f)
        except Exception as e:
            logger.warning("Embedding cache write failed: %s", e)


class EmbeddingGenerator:
    """Generates embeddings with optional caching."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", cache: Optional[EmbeddingCache] = None):
        self.model_name = model_name
        self.cache = cache or EmbeddingCache()
        self._model = None
        self._load_attempted = False
        # Why embeddings are unavailable ("" when they work). Reported by the
        # interview API instead of silently returning zero-vector results.
        self.load_error = ""

    @property
    def available(self) -> bool:
        return self.model is not None

    @property
    def model(self):
        if self._model is not None:
            return self._model
        if self._load_attempted:
            return None
        self._load_attempted = True
        ST = get_sentence_transformer_model()
        if ST is None:
            self.load_error = ("sentence-transformers could not be imported - run "
                               "`pip install sentence-transformers` (RAG semantic "
                               "retrieval disabled)")
            logger.error(self.load_error)
            return None
        try:
            self._model = ST(self.model_name)
            logger.info("RAG embeddings ready: model=%s", self.model_name)
        except Exception as e:
            self.load_error = ("embedding model %s failed to load (%s: %s)"
                               % (self.model_name, type(e).__name__, e))
            logger.error(self.load_error)
            self._model = None
        return self._model

    def embed(self, texts: List[str], use_cache: bool = True) -> np.ndarray:
        if self.model is None:
            return np.zeros((len(texts), 384), dtype=np.float32)
        results = []
        for t in texts:
            cached = self.cache.get(t) if use_cache else None
            if cached is not None:
                results.append(np.array(cached, dtype=np.float32))
            else:
                emb = self.model.encode([t], show_progress_bar=False)[0]
                results.append(np.array(emb, dtype=np.float32))
                self.cache.set(t, emb.tolist())
        return np.array(results, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return 0.0
    dot = float(np.dot(a, b))
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    return dot / norm if norm > 0 else 0.0

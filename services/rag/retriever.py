"""services/rag/retriever.py - FAISS-based retriever with embedding cache."""
import hashlib
import logging
import numpy as np
from typing import Dict, List, Optional
from services.rag.embeddings import EmbeddingGenerator, cosine_similarity

logger = logging.getLogger(__name__)

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    logger.warning("FAISS not installed; using brute-force similarity")


class FAISSRetriever:
    """Retriever using FAISS or brute-force fallback."""

    def __init__(self, embedding_generator: EmbeddingGenerator, top_k: int = 5, similarity_threshold: float = 0.3):
        self.embedding_generator = embedding_generator
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self._chunks: List[Dict] = []
        self._index = None
        self._embeddings: Optional[np.ndarray] = None

    @property
    def backend(self) -> str:
        """Which retrieval implementation is actually in use (never guessed)."""
        return "faiss" if (HAS_FAISS and self._index is not None) else "brute_force_numpy"

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @staticmethod
    def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
        """Row-wise L2 normalisation.

        IndexFlatIP computes an inner product, which only equals cosine
        similarity when both sides are unit length. Without this the stored
        "similarity" scores were raw dot products (MiniLM vectors are not unit
        length), so the similarity threshold was meaningless. Zero vectors (the
        no-embedding-model case) stay zero and therefore score below any
        positive threshold, which is what we want.
        """
        if matrix is None or matrix.size == 0:
            return matrix
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (matrix / norms).astype(np.float32)

    def index_chunks(self, chunks: List[Dict]):
        if not chunks:
            self._chunks = []
            self._index = None
            self._embeddings = None
            logger.warning("RAG: no chunks to index - retrieval will return 0 hits")
            return
        self._chunks = chunks
        chunk_texts = [c["content"] for c in chunks]
        raw = self.embedding_generator.embed(chunk_texts, use_cache=True)
        self._embeddings = self._l2_normalize(raw)
        if HAS_FAISS:
            dim = self._embeddings.shape[1]
            self._index = faiss.IndexFlatIP(dim)
            self._index.add(self._embeddings)
            logger.info("RAG: indexed %d chunks (backend=%s, embeddings=%s)", len(chunks),
                        self.backend, "ready" if getattr(self.embedding_generator, "available", True) else "UNAVAILABLE")
        else:
            self._index = None

    def retrieve(self, query: str, top_k: int = None, similarity_threshold: float = None) -> List[Dict]:
        k = top_k or self.top_k
        threshold = similarity_threshold if similarity_threshold is not None else self.similarity_threshold
        if len(self._chunks) == 0:
            return []
        query_emb = self._l2_normalize(
            self.embedding_generator.embed([query], use_cache=True))
        if HAS_FAISS and self._index is not None:
            sims, idxs = self._index.search(query_emb, min(k, len(self._chunks)))
            results = []
            for score, idx in zip(sims[0], idxs[0]):
                if idx == -1 or score < threshold:
                    continue
                results.append({
                    "content": self._chunks[idx]["content"],
                    "metadata": self._chunks[idx]["metadata"],
                    "score": float(score),
                })
            return results
        results = []
        for i, chunk in enumerate(self._chunks):
            score = cosine_similarity(query_emb[0], self._embeddings[i])
            if score >= threshold:
                results.append({"content": chunk["content"], "metadata": chunk["metadata"], "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:k]

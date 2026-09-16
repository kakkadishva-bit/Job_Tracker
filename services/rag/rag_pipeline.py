"""
services/rag/rag_pipeline.py
Top-level RAG pipeline tying loader + chunker + retriever together.
"""
from typing import List, Dict, Optional
from .pipeline import DocumentLoader, Chunker
from .retriever import FAISSRetriever
from .embeddings import EmbeddingGenerator, EmbeddingCache
import logging
import os

logger = logging.getLogger(__name__)

_rag_singleton_error = ""

_rag_instance = None


class RAGUnavailableError(Exception):
    """Raised when the RAG pipeline cannot be initialized."""


class RAGPipeline:
    """End-to-end RAG: load knowledge docs, chunk, embed, retrieve."""

    def __init__(self, knowledge_dir: str = None, cache_dir: str = None,
                 chunk_size: int = 500, top_k: int = 5,
                 similarity_threshold: float = 0.3):
        self.knowledge_dir = knowledge_dir or os.path.join(os.path.dirname(__file__), "..", "..", "data", "interview_knowledge")
        self.cache_dir = cache_dir or os.path.join(os.getcwd(), ".cache", "rag")
        self.chunker = Chunker(chunk_size=chunk_size, chunk_overlap=100)
        self.embedding_cache = EmbeddingCache(self.cache_dir)
        self.embedding_generator = EmbeddingGenerator(cache=self.embedding_cache)
        self.retriever = FAISSRetriever(
            embedding_generator=self.embedding_generator,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self._initialized = False
        self.document_count = 0
        self.chunk_count = 0
        self.last_error = ""
        self.embedding_error = ""
        self.last_query = ""
        self.last_hits = 0
        self.total_hits = 0
        self.retrieval_count = 0

    def initialize(self):
        if self._initialized:
            return
        loader = DocumentLoader(self.knowledge_dir)
        docs = loader.load_all()
        chunks = self.chunker.chunk_documents(docs)
        self.retriever.index_chunks(chunks)
        self._initialized = True
        self.document_count = len(docs)
        self.chunk_count = len(chunks)
        self.embedding_error = getattr(self.embedding_generator, "load_error", "")
        if not chunks:
            self.last_error = ("rag_empty_index: %d documents loaded from %s but 0 "
                               "chunks were indexed" % (len(docs), self.knowledge_dir))
            logger.error("RAG: %s", self.last_error)
        elif self.embedding_error:
            self.last_error = self.embedding_error
        logger.info("RAG: initialized with %d documents, %d chunks", len(docs), len(chunks))

    def retrieve(self, query: str, top_k: int = None, similarity_threshold: float = None) -> List[Dict]:
        try:
            self.initialize()
        except Exception as e:
            self.last_error = "rag_init_failed: %s: %s" % (type(e).__name__, e)
            logger.warning("RAG: initialization failed, using empty retrieval: %s", e)
            return []
        if self.retriever.chunk_count == 0:
            self.last_error = ("rag_empty_index: %d documents loaded from %s but 0 "
                               "chunks were indexed"
                               % (self.document_count, self.knowledge_dir))
            logger.warning("RAG: empty index - returning 0 hits (%s)", self.last_error)
            return []
        self.last_error = ""
        results = self.retriever.retrieve(
            query,
            top_k=top_k or self.top_k,
            similarity_threshold=similarity_threshold or self.similarity_threshold,
        )
        self.retrieval_count += 1
        self.last_query = query[:200]
        self.last_hits = len(results)
        self.total_hits += len(results)
        if not results:
            self.last_error = ("rag_no_hits: no chunk scored above the similarity "
                               "threshold %.2f" % self.similarity_threshold)
            logger.warning("RAG: 0 hits (query=%r, backend=%s, chunks=%d)", query[:80],
                           self.retriever.backend, self.retriever.chunk_count)
        return results


    def get_status(self) -> Dict:
        return {
            "available": self._initialized,
            "knowledge_dir": self.knowledge_dir,
            "top_k": self.top_k,
            "similarity_threshold": self.similarity_threshold,
            "backend": self.retriever.backend,
            "documents_indexed": self.document_count,
            "embedding_model": self.embedding_generator.model_name,
            "embeddings_available": bool(getattr(self.embedding_generator, "available", False)),
            "embedding_error": self.embedding_error,
            "retrieval_count": self.retrieval_count,
            "last_query": self.last_query,
            "last_hits": self.last_hits,
            "total_hits": self.total_hits,
            "last_error": self.last_error,
            "chunk_count": len(self.retriever._chunks),
        }


def get_rag():
    """Returns a singleton RAGPipeline configured from environment."""
    global _rag_instance, _rag_singleton_error
    if _rag_instance is not None:
        return _rag_instance
    try:
        _rag_instance = RAGPipeline()
        _rag_instance.initialize()
        logger.info("RAG: singleton pipeline initialized")
    except Exception as e:
        _rag_singleton_error = "rag_init_failed: %s: %s" % (type(e).__name__, e)
        logger.warning("RAG: failed to initialize singleton: %s", e)
        _rag_instance = None
    return _rag_instance
def last_rag_error() -> str:
    """Reason the singleton RAG pipeline is unavailable ("" when it is fine)."""
    global _rag_instance, _rag_singleton_error
    if _rag_instance is not None:
        return getattr(_rag_instance, "last_error", "") or ""
    return _rag_singleton_error

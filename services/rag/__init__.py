"""
services/rag/__init__.py
"""
from .pipeline import Document, DocumentLoader, Chunker

try:
    from .rag_pipeline import RAGPipeline, get_rag, last_rag_error, RAGUnavailableError
except ImportError:
    RAGPipeline = None
    get_rag = None
    RAGUnavailableError = Exception
    last_rag_error = None

try:
    from .retriever import EmbeddingCache, FAISSRetriever
except ImportError:
    EmbeddingCache = None
    FAISSRetriever = None

__all__ = [
    "Document", "DocumentLoader", "Chunker",
    "EmbeddingCache", "FAISSRetriever",
    "RAGPipeline", "get_rag", "last_rag_error", "RAGUnavailableError",
]

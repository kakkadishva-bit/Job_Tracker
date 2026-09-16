"""
services/rag/rag_store.py
Backend store for the RAG pipeline.
"""
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

from services.rag.embeddings import EmbeddingGenerator, EmbeddingCache
from services.rag.retriever import FAISSRetriever

logger = logging.getLogger(__name__)


class RAGStore:
    """Persistent storage for the RAG pipeline."""

    def __init__(self, index_dir: str = None):
        self.index_dir = index_dir or os.path.expanduser("~/.jobagent/rag_index")
        os.makedirs(self.index_dir, exist_ok=True)
        self.embedding_cache = EmbeddingCache(os.path.join(self.index_dir, "embedding_cache"))
        self.embedding_generator = EmbeddingGenerator(cache=self.embedding_cache)
        self.retriever = FAISSRetriever(embedding_generator=self.embedding_generator)

    def build_and_store(self, chunks: List[Dict]) -> None:
        self.retriever.index_chunks(chunks)

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        return self.retriever.retrieve(query, top_k=top_k)

    def save_rag_bundle(self, path: str) -> None:
        _dir = os.path.dirname(path)
        os.makedirs(_dir, exist_ok=True)
        _data = {
            "chunks": self.retriever._chunks,
            "created_at": datetime.utcnow().isoformat(),
        }
        with open(path, "w", encoding="utf-8") as _f:
            json.dump(_data, _f, ensure_ascii=False, indent=2, default=str)
        logger.info("RAG: saved bundle to %s", path)

    def save_rag_to_directory(self, directory: str) -> None:
        self.save_rag_bundle(os.path.join(directory, "rag_store.json"))

    def save_rag_instructions(self, pdf_path: str) -> None:
        self.save_rag_bundle(os.path.join(os.path.dirname(pdf_path), "rag_store.json"))

    def clear(self) -> None:
        self.retriever._chunks = []
        self.retriever._embeddings = None
        self.retriever._index = None
        index_path = os.path.join(self.index_dir, "_index.pkl")
        if os.path.exists(index_path):
            os.remove(index_path)
        logger.info("RAG: cleared index store")


def get_rag_store(index_dir: str = None) -> RAGStore:
    return RAGStore(index_dir=index_dir)

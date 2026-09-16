"""
services/rag/pipeline.py
Document, DocumentLoader, and Chunker for the RAG pipeline.
"""
import os
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

DEFAULT_KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "interview_knowledge")
DEFAULT_TOP_K = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.3


class Document:
    """A single source document for the RAG pipeline."""

    def __init__(self, doc_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        self.doc_id = doc_id
        self.content = content
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"doc_id": self.doc_id, "content": self.content, "metadata": self.metadata}


class DocumentLoader:
    """Loads documents from a directory for the RAG pipeline."""

    def __init__(self, knowledge_dir: Optional[str] = None):
        self.knowledge_dir = knowledge_dir or DEFAULT_KNOWLEDGE_DIR
        os.makedirs(self.knowledge_dir, exist_ok=True)

    def load_all(self) -> List[Document]:
        """Load all documents from the knowledge directory."""
        documents: List[Document] = []
        if not os.path.isdir(self.knowledge_dir):
            logger.warning("Knowledge directory not found: %s", self.knowledge_dir)
            return documents
        for filename in sorted(os.listdir(self.knowledge_dir)):
            if filename.startswith(".") or not filename.endswith((".md", ".txt", ".json")):
                continue
            filepath = os.path.join(self.knowledge_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                doc_id = os.path.splitext(filename)[0]
                documents.append(Document(doc_id=doc_id, content=content, metadata={"source": filename}))
            except Exception as e:
                logger.warning("Failed to load %s: %s", filename, e)
        logger.info("DocumentLoader: loaded %d documents from %s", len(documents), self.knowledge_dir)
        return documents


class Chunker:
    """Simple text chunker that splits documents into overlapping chunks."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_documents(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """Chunk documents into overlapping text chunks."""
        chunks: List[Dict[str, Any]] = []
        for doc in documents:
            content = doc.content
            if not content.strip():
                continue
            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
            for para in paragraphs:
                words = para.split()
                if len(words) <= self.chunk_size:
                    chunks.append({
                        "content": para,
                        "metadata": {**doc.metadata, "doc_id": doc.doc_id, "chunk_index": len(chunks)},
                    })
                    continue
                start = 0
                while start < len(words):
                    end = min(start + self.chunk_size, len(words))
                    chunk_text = " ".join(words[start:end])
                    chunks.append({
                        "content": chunk_text,
                        "metadata": {**doc.metadata, "doc_id": doc.doc_id, "chunk_index": len(chunks)},
                    })
                    if end >= len(words):
                        break
                    start = max(0, end - self.chunk_overlap)
        logger.info("Chunker: produced %d chunks from %d documents", len(chunks), len(documents))
        return chunks

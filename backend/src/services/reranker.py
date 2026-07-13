"""Optional cross-encoder reranker for document RAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from models import ResearchDocumentChunk


class Reranker(Protocol):
    def rerank(self, query: str, chunks: list[ResearchDocumentChunk], limit: int) -> list[ResearchDocumentChunk]:
        """Return chunks ordered by relevance to query."""


@dataclass
class CrossEncoderReranker:
    model_name: str

    def __post_init__(self) -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover - depends on optional runtime deps
            raise RuntimeError("Missing optional dependency: sentence-transformers") from exc
        self._model = CrossEncoder(self.model_name)

    def rerank(self, query: str, chunks: list[ResearchDocumentChunk], limit: int) -> list[ResearchDocumentChunk]:
        if not chunks:
            return []
        pairs = [(query, chunk.text) for chunk in chunks]
        scores = self._model.predict(pairs)
        scored = []
        for score, chunk in zip(scores, chunks, strict=True):
            metadata = dict(chunk.metadata)
            metadata["rerank_score"] = round(float(score), 4)
            scored.append((float(score), ResearchDocumentChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                metadata=metadata,
                embedding=chunk.embedding,
                embedding_model=chunk.embedding_model,
                embedded_at=chunk.embedded_at,
            )))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[: max(1, limit)]]


def create_reranker(model_name: str) -> Reranker:
    return CrossEncoderReranker(model_name)

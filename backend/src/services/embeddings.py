"""OpenAI-compatible embedding helpers for document RAG."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from openai import OpenAI

from config import Configuration
from models import ResearchDocumentChunk


class EmbeddingProvider(Protocol):
    model: str
    dimension: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


@dataclass
class EmbeddingService:
    config: Configuration

    @property
    def model(self) -> str:
        return self.config.embedding_model or "text-embedding-3-small"

    @property
    def dimension(self) -> int:
        return self.config.embedding_dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        payload = [text for text in texts if text]
        if not payload:
            return []
        client = OpenAI(api_key=self._api_key(), base_url=self._base_url())
        response = client.embeddings.create(model=self.model, input=payload, dimensions=self.dimension)
        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(f"Embedding dimension mismatch: expected {self.dimension}, got {len(vector)}")
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_texts([text])
        return vectors[0] if vectors else []

    def _base_url(self) -> str | None:
        if self.config.embedding_base_url:
            return self.config.embedding_base_url
        if self.config.llm_provider == "ollama":
            return self.config.sanitized_ollama_url()
        if self.config.llm_provider == "lmstudio":
            return self.config.lmstudio_base_url
        return self.config.llm_base_url

    def _api_key(self) -> str:
        return self.config.embedding_api_key or self.config.llm_api_key or "not-needed"


def attach_embeddings(
    chunks: list[ResearchDocumentChunk],
    embedding_service: EmbeddingProvider | None,
) -> tuple[list[ResearchDocumentChunk], str | None]:
    if embedding_service is None or not chunks:
        return chunks, None
    try:
        vectors = embedding_service.embed_texts([chunk.text for chunk in chunks])
    except Exception as exc:  # noqa: BLE001 - embedding failure should not block document upload
        return chunks, str(exc)

    embedded_at = datetime.now(timezone.utc)
    updated: list[ResearchDocumentChunk] = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        metadata = dict(chunk.metadata)
        metadata.update(
            {
                "has_embedding": True,
                "embedding_model": embedding_service.model,
                "embedded_at": embedded_at.isoformat(),
            }
        )
        updated.append(
            ResearchDocumentChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                metadata=metadata,
                embedding=vector,
                embedding_model=embedding_service.model,
                embedded_at=embedded_at,
            )
        )
    return updated, None


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, dot / (left_norm * right_norm))

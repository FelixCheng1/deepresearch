"""文档库 RAG 检索边界。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from config import Configuration
from models import ResearchDocumentChunk
from services.embeddings import EmbeddingProvider, EmbeddingService
from services.repository import ResearchRepository


class Retriever(Protocol):
    """为数据库和上传文档 RAG 预留的检索接口。"""

    def retrieve(self, query: str) -> list[ResearchDocumentChunk]:
        """返回与查询相关的文档片段。"""


@dataclass
class DisabledRetriever:
    """RAG 关闭时使用的空检索器。"""

    config: Configuration
    calls: list[str] = field(default_factory=list)

    def retrieve(self, query: str) -> list[ResearchDocumentChunk]:
        self.calls.append(query)
        return []


@dataclass
class RepositoryRetriever:
    """基于文档仓库的简单文本检索器。"""

    repository: ResearchRepository
    limit: int = 5
    min_score: float = 0.0
    embedding_service: EmbeddingProvider | None = None
    calls: list[str] = field(default_factory=list)

    def retrieve(self, query: str) -> list[ResearchDocumentChunk]:
        self.calls.append(query)
        query_embedding = None
        if self.embedding_service is not None:
            try:
                query_embedding = self.embedding_service.embed_query(query)
            except Exception:
                query_embedding = None
        return self.repository.search_document_chunks(
            query,
            limit=self.limit,
            min_score=self.min_score,
            query_embedding=query_embedding,
        )


def create_retriever(config: Configuration, repository: ResearchRepository) -> Retriever:
    """根据 RAG 开关创建检索器。"""

    if not config.rag_enabled:
        return DisabledRetriever(config)
    embedding_service = EmbeddingService(config) if config.database_url and config.embedding_model else None
    return RepositoryRetriever(
        repository=repository,
        limit=max(1, min(config.rag_top_k, 20)),
        min_score=max(0.0, config.rag_min_score),
        embedding_service=embedding_service,
    )

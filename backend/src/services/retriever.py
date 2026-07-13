"""文档库 RAG 检索边界。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

from config import Configuration
from models import ResearchDocumentChunk
from services.embeddings import EmbeddingProvider, EmbeddingService
from services.repository import ResearchRepository
from services.reranker import Reranker, create_reranker

logger = logging.getLogger(__name__)


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
    reranker: Reranker | None = None
    rerank_top_n: int = 20
    calls: list[str] = field(default_factory=list)

    def retrieve(self, query: str) -> list[ResearchDocumentChunk]:
        self.calls.append(query)
        query_embedding = None
        if self.embedding_service is not None:
            try:
                query_embedding = self.embedding_service.embed_query(query)
            except Exception as exc:
                logger.warning("Query embedding failed; falling back to lexical retrieval: %s", exc)
                query_embedding = None
        candidate_limit = self.rerank_top_n if self.reranker is not None else self.limit
        chunks = self.repository.search_document_chunks(
            query,
            limit=candidate_limit,
            min_score=self.min_score,
            query_embedding=query_embedding,
        )
        if self.reranker is None:
            return chunks[: self.limit]
        try:
            return self.reranker.rerank(query, chunks, self.limit)
        except Exception as exc:
            logger.warning("Reranking failed; keeping first-stage ranking: %s", exc)
            return chunks[: self.limit]


def create_retriever(config: Configuration, repository: ResearchRepository) -> Retriever:
    """根据 RAG 开关创建检索器。"""

    if not config.rag_enabled:
        return DisabledRetriever(config)
    embedding_service = EmbeddingService(config) if config.database_url and config.embedding_model else None
    reranker = None
    if config.rag_rerank_enabled:
        try:
            reranker = create_reranker(config.rag_rerank_model)
        except Exception as exc:
            logger.warning("Reranker initialization failed; reranking is disabled: %s", exc)
            reranker = None
    return RepositoryRetriever(
        repository=repository,
        limit=max(1, min(config.rag_top_k, 20)),
        min_score=max(0.0, config.rag_min_score),
        embedding_service=embedding_service,
        reranker=reranker,
        rerank_top_n=max(config.rag_top_k, min(config.rag_rerank_top_n, 50)),
    )

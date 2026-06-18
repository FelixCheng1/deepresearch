"""为未来 RAG 预留的检索边界。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from config import Configuration
from models import ResearchDocumentChunk


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

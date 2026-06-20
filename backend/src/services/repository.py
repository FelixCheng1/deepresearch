"""研究数据与文档库的持久化边界。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, joinedload, sessionmaker

from config import Configuration
from models import (
    ResearchDocument,
    ResearchDocumentChunk,
    ResearchReport,
    ResearchRun,
    ResearchSource,
    ResearchTask,
)
from services.chunker import chunk_text
from services.database import (
    DocumentChunkRow,
    DocumentRow,
    ResearchReportRow,
    ResearchRunRow,
    ResearchSourceRow,
    ResearchTaskRow,
    create_database_engine,
    create_session_factory,
)


class ResearchRepository(Protocol):
    """研究数据和文档库的存储协议。"""

    def save_run(self, run: ResearchRun) -> None:
        """保存一次研究运行的元数据。"""

    def save_task(self, task: ResearchTask) -> None:
        """保存任务快照。"""

    def save_source(self, source: ResearchSource) -> None:
        """保存来源快照。"""

    def save_report(self, report: ResearchReport) -> None:
        """保存报告快照。"""

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """按创建时间倒序列出研究运行。"""

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """读取一次研究运行及其任务、来源和报告。"""

    def save_document(
        self,
        *,
        filename: str,
        content_type: str,
        raw_text: str,
        size_bytes: int,
    ) -> ResearchDocument:
        """保存上传文档并写入切块。"""

    def list_documents(self, limit: int = 50) -> list[dict[str, Any]]:
        """按创建时间倒序列出文档库文件。"""

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        """读取单个文档及其切块。"""

    def delete_document(self, document_id: str) -> bool:
        """删除单个文档及其切块。"""

    def search_document_chunks(self, query: str, limit: int = 5, min_score: float = 0.0) -> list[ResearchDocumentChunk]:
        """用简单文本匹配检索文档片段。"""


@dataclass
class InMemoryResearchRepository:
    """未配置数据库时使用的简单内存仓库。"""

    runs: dict[str, ResearchRun] = field(default_factory=dict)
    tasks: dict[tuple[str, int], ResearchTask] = field(default_factory=dict)
    sources: list[ResearchSource] = field(default_factory=list)
    reports: dict[str, ResearchReport] = field(default_factory=dict)
    documents: dict[str, ResearchDocument] = field(default_factory=dict)

    def save_run(self, run: ResearchRun) -> None:
        self.runs[run.id] = run

    def save_task(self, task: ResearchTask) -> None:
        self.tasks[(task.run_id, task.task_id)] = task

    def save_source(self, source: ResearchSource) -> None:
        self.sources.append(source)

    def save_report(self, report: ResearchReport) -> None:
        self.reports[report.run_id] = report

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        runs = sorted(self.runs.values(), key=lambda item: item.created_at, reverse=True)
        return [self._run_summary(run) for run in runs[:limit]]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.runs.get(run_id)
        if not run:
            return None

        tasks = [
            task
            for (task_run_id, _), task in sorted(self.tasks.items(), key=lambda item: item[0][1])
            if task_run_id == run_id
        ]
        sources = [source for source in self.sources if source.run_id == run_id]
        report = self.reports.get(run_id)
        return {
            **self._run_summary(run),
            "tasks": [_task_to_dict(task) for task in tasks],
            "sources": [_source_to_dict(source) for source in sources],
            "report": _report_to_dict(report) if report else None,
        }

    def save_document(
        self,
        *,
        filename: str,
        content_type: str,
        raw_text: str,
        size_bytes: int,
    ) -> ResearchDocument:
        document = _build_document(
            filename=filename,
            content_type=content_type,
            raw_text=raw_text,
            size_bytes=size_bytes,
        )
        self.documents[document.id] = document
        return document

    def list_documents(self, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 100))
        documents = sorted(self.documents.values(), key=lambda item: item.created_at, reverse=True)
        return [_document_to_summary(document) for document in documents[:safe_limit]]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        document = self.documents.get(document_id)
        if document is None:
            return None
        return _document_to_detail(document)

    def delete_document(self, document_id: str) -> bool:
        if document_id not in self.documents:
            return False
        del self.documents[document_id]
        return True

    def search_document_chunks(self, query: str, limit: int = 5, min_score: float = 0.0) -> list[ResearchDocumentChunk]:
        chunks = [chunk for document in self.documents.values() for chunk in document.chunks]
        return _rank_chunks(query, chunks, limit=limit, min_score=min_score)

    def _run_summary(self, run: ResearchRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "topic": run.topic,
            "search_api": run.search_api,
            "created_at": run.created_at.isoformat(),
        }


class PostgresResearchRepository:
    """使用 SQLAlchemy 同步会话保存研究历史和文档库。"""

    def __init__(
        self,
        database_url: str | None = None,
        *,
        engine: Engine | None = None,
        session_factory: sessionmaker | None = None,
    ) -> None:
        if session_factory is not None:
            self._session_factory = session_factory
            return

        if engine is None:
            if not database_url:
                raise ValueError("缺少 DATABASE_URL，无法创建 Postgres 仓库")
            engine = create_database_engine(database_url)
        self._session_factory = create_session_factory(engine)

    def save_run(self, run: ResearchRun) -> None:
        with self._session() as session:
            row = session.get(ResearchRunRow, run.id)
            if row is None:
                row = ResearchRunRow(
                    id=run.id,
                    topic=run.topic,
                    search_api=run.search_api,
                    created_at=run.created_at,
                )
                session.add(row)
            else:
                row.topic = run.topic
                row.search_api = run.search_api
                row.created_at = run.created_at
            session.commit()

    def save_task(self, task: ResearchTask) -> None:
        with self._session() as session:
            existing = session.scalar(
                select(ResearchTaskRow).where(
                    ResearchTaskRow.run_id == task.run_id,
                    ResearchTaskRow.task_id == task.task_id,
                )
            )
            if existing is None:
                existing = ResearchTaskRow(run_id=task.run_id, task_id=task.task_id)
                session.add(existing)

            existing.title = task.title
            existing.intent = task.intent
            existing.query = task.query
            existing.status = task.status
            existing.note_id = task.note_id
            existing.note_path = task.note_path
            session.commit()

    def save_source(self, source: ResearchSource) -> None:
        with self._session() as session:
            session.add(
                ResearchSourceRow(
                    run_id=source.run_id,
                    task_id=source.task_id,
                    title=source.title,
                    url=source.url,
                    content=source.content,
                )
            )
            session.commit()

    def save_report(self, report: ResearchReport) -> None:
        with self._session() as session:
            row = session.get(ResearchReportRow, report.run_id)
            if row is None:
                row = ResearchReportRow(run_id=report.run_id, markdown=report.markdown)
                session.add(row)
            row.markdown = report.markdown
            row.note_id = report.note_id
            row.note_path = report.note_path
            session.commit()

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 100))
        with self._session() as session:
            rows = session.scalars(
                select(ResearchRunRow)
                .order_by(ResearchRunRow.created_at.desc())
                .limit(safe_limit)
            ).all()
            return [_run_row_to_summary(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._session() as session:
            stmt = (
                select(ResearchRunRow)
                .where(ResearchRunRow.id == run_id)
                .options(
                    joinedload(ResearchRunRow.tasks),
                    joinedload(ResearchRunRow.sources),
                    joinedload(ResearchRunRow.report),
                )
            )
            row = session.execute(stmt).unique().scalar_one_or_none()
            if row is None:
                return None

            return {
                **_run_row_to_summary(row),
                "tasks": [_task_row_to_dict(task) for task in row.tasks],
                "sources": [_source_row_to_dict(source) for source in row.sources],
                "report": _report_row_to_dict(row.report) if row.report else None,
            }

    def save_document(
        self,
        *,
        filename: str,
        content_type: str,
        raw_text: str,
        size_bytes: int,
    ) -> ResearchDocument:
        document = _build_document(
            filename=filename,
            content_type=content_type,
            raw_text=raw_text,
            size_bytes=size_bytes,
        )
        with self._session() as session:
            row = DocumentRow(
                id=document.id,
                filename=document.filename,
                content_type=document.content_type,
                size_bytes=document.size_bytes,
                raw_text=document.raw_text,
                summary=document.summary,
                created_at=document.created_at,
            )
            row.chunks = [
                DocumentChunkRow(
                    id=chunk.id,
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    chunk_metadata=chunk.metadata,
                )
                for chunk in document.chunks
            ]
            session.add(row)
            session.commit()
        return document

    def list_documents(self, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 100))
        with self._session() as session:
            rows = session.scalars(
                select(DocumentRow)
                .order_by(DocumentRow.created_at.desc())
                .limit(safe_limit)
                .options(joinedload(DocumentRow.chunks))
            ).unique().all()
            return [_document_row_to_summary(row) for row in rows]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.execute(
                select(DocumentRow)
                .where(DocumentRow.id == document_id)
                .options(joinedload(DocumentRow.chunks))
            ).unique().scalar_one_or_none()
            if row is None:
                return None
            return _document_row_to_detail(row)

    def delete_document(self, document_id: str) -> bool:
        with self._session() as session:
            row = session.get(DocumentRow, document_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def search_document_chunks(self, query: str, limit: int = 5, min_score: float = 0.0) -> list[ResearchDocumentChunk]:
        with self._session() as session:
            rows = session.execute(
                select(DocumentChunkRow)
                .join(DocumentChunkRow.document)
                .options(joinedload(DocumentChunkRow.document))
            ).scalars().all()
            chunks = [_chunk_row_to_model(row) for row in rows]
        return _rank_chunks(query, chunks, limit=limit, min_score=min_score)

    def _session(self) -> Session:
        return self._session_factory()


def create_research_repository(config: Configuration) -> ResearchRepository:
    """根据配置创建研究仓库。"""

    if config.database_url:
        return PostgresResearchRepository(database_url=config.database_url)
    return InMemoryResearchRepository()


def _build_document(*, filename: str, content_type: str, raw_text: str, size_bytes: int) -> ResearchDocument:
    document_id = uuid4().hex
    chunks = [
        ResearchDocumentChunk(
            id=uuid4().hex,
            document_id=document_id,
            document_title=filename,
            chunk_index=index,
            text=text,
            metadata={"filename": filename, "chunk_index": index},
        )
        for index, text in enumerate(chunk_text(raw_text), start=1)
    ]
    summary = _summarize_text(raw_text)
    return ResearchDocument(
        id=document_id,
        filename=filename,
        content_type=content_type or _content_type_for_filename(filename),
        size_bytes=size_bytes,
        raw_text=raw_text,
        summary=summary,
        created_at=datetime.now(timezone.utc),
        chunks=chunks,
    )


def _content_type_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".md":
        return "text/markdown"
    return "text/plain"


def _summarize_text(text: str, limit: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


def _rank_chunks(
    query: str,
    chunks: list[ResearchDocumentChunk],
    *,
    limit: int,
    min_score: float = 0.0,
) -> list[ResearchDocumentChunk]:
    query_profile = _build_query_profile(query)
    safe_limit = max(1, min(limit, 20))
    if not query_profile["terms"] and not query_profile["phrases"]:
        return chunks[:safe_limit]

    avg_len = max(1.0, sum(_chunk_length(chunk) for chunk in chunks) / max(1, len(chunks)))
    scored: list[tuple[float, ResearchDocumentChunk]] = []
    for chunk in chunks:
        score, matched_terms = _score_chunk(chunk, query_profile, avg_len)
        if score < min_score:
            continue
        metadata = dict(chunk.metadata)
        metadata.update(
            {
                "score": round(score, 4),
                "matched_terms": matched_terms,
                "snippet": _best_snippet(chunk.text, query_profile),
            }
        )
        scored.append(
            (
                score,
                ResearchDocumentChunk(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    document_title=chunk.document_title,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    metadata=metadata,
                ),
            )
        )

    scored.sort(key=lambda item: (-item[0], item[1].document_title, item[1].chunk_index))
    return [chunk for _, chunk in scored[:safe_limit]]


def _build_query_profile(query: str) -> dict[str, list[str]]:
    normalized = _normalize_for_search(query)
    words = re.findall(r"[a-z0-9]+", normalized)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    cjk_bigrams = ["".join(cjk_chars[index : index + 2]) for index in range(max(0, len(cjk_chars) - 1))]
    terms = _dedupe([term for term in words + cjk_bigrams if len(term) > 1])
    phrases = _dedupe([part for part in re.split(r"\s+", normalized) if len(part) >= 4])
    if len(cjk_chars) >= 3:
        phrases.append("".join(cjk_chars))
    return {"terms": terms, "phrases": _dedupe(phrases)}


def _score_chunk(
    chunk: ResearchDocumentChunk,
    query_profile: dict[str, list[str]],
    avg_len: float,
) -> tuple[float, list[str]]:
    title = _normalize_for_search(chunk.document_title)
    body = _normalize_for_search(chunk.text)
    title_tokens = _tokenize_text(title)
    body_tokens = _tokenize_text(body)
    body_len = max(1, len(body_tokens))
    k1 = 1.4
    b = 0.72
    score = 0.0
    matched: list[str] = []

    for term in query_profile["terms"]:
        tf = body_tokens.count(term)
        title_tf = title_tokens.count(term)
        substring_hit = 1 if term in body and tf == 0 else 0
        frequency = tf + substring_hit + title_tf * 2.4
        if frequency <= 0:
            continue
        bm25 = (frequency * (k1 + 1)) / (frequency + k1 * (1 - b + b * body_len / avg_len))
        score += bm25
        if title_tf:
            score += 1.2
        matched.append(term)

    for phrase in query_profile["phrases"]:
        if phrase and phrase in f"{title}\n{body}":
            score += 2.5 if phrase in title else 1.6
            matched.append(phrase)

    if query_profile["terms"]:
        coverage = len(set(matched) & set(query_profile["terms"])) / len(query_profile["terms"])
        score += coverage * 2.0

    if body_len > avg_len * 1.8:
        score *= 0.92
    return score, _dedupe(matched)[:8]


def _tokenize_text(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", text)
    cjk_bigrams = ["".join(cjk_chars[index : index + 2]) for index in range(max(0, len(cjk_chars) - 1))]
    return words + cjk_bigrams


def _normalize_for_search(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _chunk_length(chunk: ResearchDocumentChunk) -> int:
    return max(1, len(_tokenize_text(_normalize_for_search(chunk.text))))


def _best_snippet(text: str, query_profile: dict[str, list[str]], *, max_chars: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    haystack = _normalize_for_search(compact)
    positions = [haystack.find(term) for term in query_profile["terms"] + query_profile["phrases"] if term and haystack.find(term) >= 0]
    start = max(0, min(positions) - 60) if positions else 0
    snippet = compact[start : start + max_chars].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if start + max_chars < len(compact):
        snippet = f"{snippet}..."
    return snippet


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _tokenize(query: str) -> list[str]:
    return _build_query_profile(query)["terms"]


def _task_to_dict(task: ResearchTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "intent": task.intent,
        "query": task.query,
        "status": task.status,
        "note_id": task.note_id,
        "note_path": task.note_path,
    }


def _source_to_dict(source: ResearchSource) -> dict[str, Any]:
    return {
        "task_id": source.task_id,
        "title": source.title,
        "url": source.url,
        "content": source.content,
    }


def _report_to_dict(report: ResearchReport) -> dict[str, Any]:
    return {
        "markdown": report.markdown,
        "note_id": report.note_id,
        "note_path": report.note_path,
    }


def _run_row_to_summary(row: ResearchRunRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "topic": row.topic,
        "search_api": row.search_api,
        "created_at": row.created_at.isoformat(),
    }


def _task_row_to_dict(row: ResearchTaskRow) -> dict[str, Any]:
    return {
        "task_id": row.task_id,
        "title": row.title,
        "intent": row.intent,
        "query": row.query,
        "status": row.status,
        "note_id": row.note_id,
        "note_path": row.note_path,
    }


def _source_row_to_dict(row: ResearchSourceRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "title": row.title,
        "url": row.url,
        "content": row.content,
    }


def _report_row_to_dict(row: ResearchReportRow) -> dict[str, Any]:
    return {
        "markdown": row.markdown,
        "note_id": row.note_id,
        "note_path": row.note_path,
    }


def _document_to_summary(document: ResearchDocument) -> dict[str, Any]:
    return {
        "id": document.id,
        "filename": document.filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "summary": document.summary,
        "created_at": document.created_at.isoformat(),
        "chunk_count": len(document.chunks),
    }


def _document_to_detail(document: ResearchDocument) -> dict[str, Any]:
    return {
        **_document_to_summary(document),
        "raw_text": document.raw_text,
        "chunks": [_chunk_to_dict(chunk) for chunk in document.chunks],
    }


def _chunk_to_dict(chunk: ResearchDocumentChunk) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "document_title": chunk.document_title,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "metadata": chunk.metadata,
    }


def _document_row_to_summary(row: DocumentRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "filename": row.filename,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "summary": row.summary,
        "created_at": row.created_at.isoformat(),
        "chunk_count": len(row.chunks),
    }


def _document_row_to_detail(row: DocumentRow) -> dict[str, Any]:
    return {
        **_document_row_to_summary(row),
        "raw_text": row.raw_text,
        "chunks": [_chunk_row_to_dict(chunk) for chunk in row.chunks],
    }


def _chunk_row_to_dict(row: DocumentChunkRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "document_id": row.document_id,
        "document_title": row.document.filename,
        "chunk_index": row.chunk_index,
        "text": row.text,
        "metadata": row.chunk_metadata or {},
    }


def _chunk_row_to_model(row: DocumentChunkRow) -> ResearchDocumentChunk:
    return ResearchDocumentChunk(
        id=row.id,
        document_id=row.document_id,
        document_title=row.document.filename,
        chunk_index=row.chunk_index,
        text=row.text,
        metadata=row.chunk_metadata or {},
    )

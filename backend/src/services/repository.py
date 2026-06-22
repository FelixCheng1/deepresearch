"""Persistence boundary for research data and document library."""

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
from services.embeddings import EmbeddingProvider, attach_embeddings, cosine_similarity
from services.database import (
    DocumentChunkRow,
    DocumentJobRow,
    DocumentRow,
    ResearchReportRow,
    ResearchRunRow,
    ResearchSourceRow,
    ResearchTaskRow,
    create_database_engine,
    create_session_factory,
)


class ResearchRepository(Protocol):
    """Storage protocol for research data and document library."""

    def save_run(self, run: ResearchRun) -> None:
        """Save research run metadata."""

    def save_task(self, task: ResearchTask) -> None:
        """Save task snapshot."""

    def save_source(self, source: ResearchSource) -> None:
        """Save source snapshot."""

    def save_report(self, report: ResearchReport) -> None:
        """Save report snapshot."""

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """List research runs by creation time descending."""

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Read one research run with tasks, sources and report."""

    def save_document(
        self,
        *,
        filename: str,
        content_type: str,
        raw_text: str,
        size_bytes: int,
    ) -> ResearchDocument:
        """Save an uploaded document and chunks."""

    def create_pending_document(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> ResearchDocument:
        """Create a document record that is waiting for background parsing."""

    def complete_document_processing(
        self,
        document_id: str,
        *,
        raw_text: str,
        content_type: str,
    ) -> bool:
        """Persist parsed text, chunks and embeddings for a document."""

    def fail_document_processing(self, document_id: str, error_message: str) -> bool:
        """Mark a document as failed after background parsing."""

    def enqueue_document_job(self, document_id: str, payload: bytes, job_type: str = "parse") -> dict[str, Any]:
        """Create a pending document job."""

    def claim_next_document_job(self) -> dict[str, Any] | None:
        """Mark and return the oldest pending document job."""

    def succeed_document_job(self, job_id: str) -> bool:
        """Mark a document job as succeeded."""

    def fail_document_job(self, job_id: str, error_message: str) -> bool:
        """Mark a document job as failed."""

    def retry_failed_document(self, document_id: str) -> dict[str, Any] | None:
        """Create a new pending job for a failed document."""

    def reset_running_document_jobs(self) -> int:
        """Move abandoned running jobs back to pending."""

    def rebuild_document(self, document_id: str) -> bool:
        """Rebuild chunks and embeddings from stored raw text."""

    def list_documents(self, limit: int = 50) -> list[dict[str, Any]]:
        """List uploaded documents by creation time descending."""

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        """Read a document and its chunks."""

    def delete_document(self, document_id: str) -> bool:
        """Delete a document and its chunks."""

    def search_document_chunks(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
        query_embedding: list[float] | None = None,
    ) -> list[ResearchDocumentChunk]:
        """Search document chunks with text/vector signals."""


@dataclass
class InMemoryResearchRepository:
    """Simple in-memory repository used when no database is configured."""

    runs: dict[str, ResearchRun] = field(default_factory=dict)
    tasks: dict[tuple[str, int], ResearchTask] = field(default_factory=dict)
    sources: list[ResearchSource] = field(default_factory=list)
    reports: dict[str, ResearchReport] = field(default_factory=dict)
    documents: dict[str, ResearchDocument] = field(default_factory=dict)
    document_jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    embedding_service: EmbeddingProvider | None = None

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
            embedding_service=self.embedding_service,
        )
        self.documents[document.id] = document
        return document

    def create_pending_document(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> ResearchDocument:
        document = ResearchDocument(
            id=uuid4().hex,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            raw_text="",
            summary=None,
            status="processing",
            created_at=datetime.now(timezone.utc),
            chunks=[],
        )
        self.documents[document.id] = document
        return document

    def complete_document_processing(
        self,
        document_id: str,
        *,
        raw_text: str,
        content_type: str,
    ) -> bool:
        existing = self.documents.get(document_id)
        if existing is None:
            return False
        document = _build_document(
            filename=existing.filename,
            content_type=content_type,
            raw_text=raw_text,
            size_bytes=existing.size_bytes,
            embedding_service=self.embedding_service,
            document_id=document_id,
            created_at=existing.created_at,
        )
        self.documents[document_id] = document
        return True

    def fail_document_processing(self, document_id: str, error_message: str) -> bool:
        document = self.documents.get(document_id)
        if document is None:
            return False
        document.status = "failed"
        document.error_message = error_message
        document.processed_at = datetime.now(timezone.utc)
        document.chunks = []
        return True

    def enqueue_document_job(self, document_id: str, payload: bytes, job_type: str = "parse") -> dict[str, Any]:
        document = self.documents.get(document_id)
        if document is None:
            raise ValueError("document not found")
        now = datetime.now(timezone.utc)
        job = {
            "id": uuid4().hex,
            "document_id": document_id,
            "filename": document.filename,
            "content_type": document.content_type,
            "job_type": job_type,
            "status": "pending",
            "error_message": None,
            "attempts": 0,
            "payload": payload,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
        }
        self.document_jobs[job["id"]] = job
        return _document_job_to_dict(job)

    def claim_next_document_job(self) -> dict[str, Any] | None:
        pending = [job for job in self.document_jobs.values() if job["status"] == "pending"]
        if not pending:
            return None
        job = sorted(pending, key=lambda item: item["created_at"])[0]
        document = self.documents.get(job["document_id"])
        if document is None:
            job["status"] = "failed"
            job["error_message"] = "document not found"
            job["finished_at"] = datetime.now(timezone.utc)
            return None
        job["status"] = "running"
        job["attempts"] += 1
        job["started_at"] = datetime.now(timezone.utc)
        job["filename"] = document.filename
        job["content_type"] = document.content_type
        return _document_job_to_dict(job)

    def succeed_document_job(self, job_id: str) -> bool:
        job = self.document_jobs.get(job_id)
        if job is None:
            return False
        job["status"] = "succeeded"
        job["error_message"] = None
        job["finished_at"] = datetime.now(timezone.utc)
        return True

    def fail_document_job(self, job_id: str, error_message: str) -> bool:
        job = self.document_jobs.get(job_id)
        if job is None:
            return False
        job["status"] = "failed"
        job["error_message"] = error_message
        job["finished_at"] = datetime.now(timezone.utc)
        return True

    def retry_failed_document(self, document_id: str) -> dict[str, Any] | None:
        document = self.documents.get(document_id)
        if document is None or document.status != "failed":
            return None
        latest = sorted(
            [job for job in self.document_jobs.values() if job["document_id"] == document_id and job.get("payload")],
            key=lambda item: item["created_at"],
            reverse=True,
        )
        if not latest:
            return None
        document.status = "processing"
        document.error_message = None
        document.processed_at = None
        document.chunks = []
        return self.enqueue_document_job(document_id, latest[0]["payload"], latest[0].get("job_type", "parse"))

    def reset_running_document_jobs(self) -> int:
        count = 0
        for job in self.document_jobs.values():
            if job["status"] == "running":
                job["status"] = "pending"
                job["started_at"] = None
                count += 1
        return count

    def rebuild_document(self, document_id: str) -> bool:
        existing = self.documents.get(document_id)
        if existing is None or not existing.raw_text:
            return False
        rebuilt = _build_document(
            filename=existing.filename,
            content_type=existing.content_type,
            raw_text=existing.raw_text,
            size_bytes=existing.size_bytes,
            embedding_service=self.embedding_service,
            document_id=document_id,
            created_at=existing.created_at,
        )
        self.documents[document_id] = rebuilt
        return True

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

    def search_document_chunks(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
        query_embedding: list[float] | None = None,
    ) -> list[ResearchDocumentChunk]:
        chunks = [chunk for document in self.documents.values() for chunk in document.chunks]
        return _rank_chunks(query, chunks, limit=limit, min_score=min_score, query_embedding=query_embedding)

    def _run_summary(self, run: ResearchRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "topic": run.topic,
            "search_api": run.search_api,
            "created_at": run.created_at.isoformat(),
        }


class PostgresResearchRepository:
    """SQLAlchemy repository for research history and document library."""

    def __init__(
        self,
        database_url: str | None = None,
        *,
        engine: Engine | None = None,
        session_factory: sessionmaker | None = None,
        embedding_service: EmbeddingProvider | None = None,
    ) -> None:
        self.embedding_service = embedding_service
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
            embedding_service=self.embedding_service,
        )
        with self._session() as session:
            row = DocumentRow(
                id=document.id,
                filename=document.filename,
                content_type=document.content_type,
                size_bytes=document.size_bytes,
                raw_text=document.raw_text,
                summary=document.summary,
                status=document.status,
                error_message=document.error_message,
                processed_at=document.processed_at,
                created_at=document.created_at,
            )
            row.chunks = [
                DocumentChunkRow(
                    id=chunk.id,
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    chunk_metadata=chunk.metadata,
                    embedding=chunk.embedding,
                    embedding_model=chunk.embedding_model,
                    embedded_at=chunk.embedded_at,
                )
                for chunk in document.chunks
            ]
            session.add(row)
            session.commit()
        return document

    def create_pending_document(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> ResearchDocument:
        document = ResearchDocument(
            id=uuid4().hex,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            raw_text="",
            summary=None,
            status="processing",
            created_at=datetime.now(timezone.utc),
            chunks=[],
        )
        with self._session() as session:
            session.add(
                DocumentRow(
                    id=document.id,
                    filename=document.filename,
                    content_type=document.content_type,
                    size_bytes=document.size_bytes,
                    raw_text=None,
                    summary=None,
                    status="processing",
                    created_at=document.created_at,
                )
            )
            session.commit()
        return document

    def complete_document_processing(
        self,
        document_id: str,
        *,
        raw_text: str,
        content_type: str,
    ) -> bool:
        with self._session() as session:
            row = session.get(DocumentRow, document_id)
            if row is None:
                return False
            document = _build_document(
                filename=row.filename,
                content_type=content_type,
                raw_text=raw_text,
                size_bytes=row.size_bytes,
                embedding_service=self.embedding_service,
                document_id=document_id,
                created_at=row.created_at,
            )
            row.content_type = document.content_type
            row.raw_text = document.raw_text
            row.summary = document.summary
            row.status = "ready"
            row.error_message = None
            row.processed_at = document.processed_at
            row.chunks = [
                DocumentChunkRow(
                    id=chunk.id,
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    chunk_metadata=chunk.metadata,
                    embedding=chunk.embedding,
                    embedding_model=chunk.embedding_model,
                    embedded_at=chunk.embedded_at,
                )
                for chunk in document.chunks
            ]
            session.commit()
            return True

    def fail_document_processing(self, document_id: str, error_message: str) -> bool:
        with self._session() as session:
            row = session.get(DocumentRow, document_id)
            if row is None:
                return False
            row.status = "failed"
            row.error_message = error_message
            row.processed_at = datetime.now(timezone.utc)
            row.chunks = []
            session.commit()
            return True

    def enqueue_document_job(self, document_id: str, payload: bytes, job_type: str = "parse") -> dict[str, Any]:
        with self._session() as session:
            document = session.get(DocumentRow, document_id)
            if document is None:
                raise ValueError("document not found")
            job = DocumentJobRow(
                id=uuid4().hex,
                document_id=document_id,
                job_type=job_type,
                status="pending",
                payload=payload,
                created_at=datetime.now(timezone.utc),
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return _document_job_row_to_dict(job)

    def claim_next_document_job(self) -> dict[str, Any] | None:
        with self._session() as session:
            job = session.scalars(
                select(DocumentJobRow)
                .where(DocumentJobRow.status == "pending")
                .order_by(DocumentJobRow.created_at)
                .limit(1)
            ).first()
            if job is None:
                return None
            document = session.get(DocumentRow, job.document_id)
            if document is None:
                job.status = "failed"
                job.error_message = "document not found"
                job.finished_at = datetime.now(timezone.utc)
                session.commit()
                return None
            job.status = "running"
            job.attempts += 1
            job.started_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(job)
            return _document_job_row_to_dict(job)

    def succeed_document_job(self, job_id: str) -> bool:
        with self._session() as session:
            job = session.get(DocumentJobRow, job_id)
            if job is None:
                return False
            job.status = "succeeded"
            job.error_message = None
            job.finished_at = datetime.now(timezone.utc)
            session.commit()
            return True

    def fail_document_job(self, job_id: str, error_message: str) -> bool:
        with self._session() as session:
            job = session.get(DocumentJobRow, job_id)
            if job is None:
                return False
            job.status = "failed"
            job.error_message = error_message
            job.finished_at = datetime.now(timezone.utc)
            session.commit()
            return True

    def retry_failed_document(self, document_id: str) -> dict[str, Any] | None:
        with self._session() as session:
            document = session.get(DocumentRow, document_id)
            if document is None or document.status != "failed":
                return None
            latest = session.scalars(
                select(DocumentJobRow)
                .where(DocumentJobRow.document_id == document_id, DocumentJobRow.payload.is_not(None))
                .order_by(DocumentJobRow.created_at.desc())
                .limit(1)
            ).first()
            if latest is None or latest.payload is None:
                return None
            document.status = "processing"
            document.error_message = None
            document.processed_at = None
            document.chunks = []
            job = DocumentJobRow(
                id=uuid4().hex,
                document_id=document_id,
                job_type=latest.job_type,
                status="pending",
                payload=latest.payload,
                created_at=datetime.now(timezone.utc),
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return _document_job_row_to_dict(job)

    def reset_running_document_jobs(self) -> int:
        with self._session() as session:
            rows = session.scalars(select(DocumentJobRow).where(DocumentJobRow.status == "running")).all()
            for row in rows:
                row.status = "pending"
                row.started_at = None
            session.commit()
            return len(rows)

    def rebuild_document(self, document_id: str) -> bool:
        with self._session() as session:
            row = session.get(DocumentRow, document_id)
            if row is None or not row.raw_text:
                return False
            document = _build_document(
                filename=row.filename,
                content_type=row.content_type,
                raw_text=row.raw_text,
                size_bytes=row.size_bytes,
                embedding_service=self.embedding_service,
                document_id=document_id,
                created_at=row.created_at,
            )
            row.raw_text = document.raw_text
            row.summary = document.summary
            row.status = "ready"
            row.error_message = None
            row.processed_at = document.processed_at
            row.chunks = [
                DocumentChunkRow(
                    id=chunk.id,
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    chunk_metadata=chunk.metadata,
                    embedding=chunk.embedding,
                    embedding_model=chunk.embedding_model,
                    embedded_at=chunk.embedded_at,
                )
                for chunk in document.chunks
            ]
            session.commit()
            return True

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

    def search_document_chunks(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
        query_embedding: list[float] | None = None,
    ) -> list[ResearchDocumentChunk]:
        with self._session() as session:
            rows = session.execute(
                select(DocumentChunkRow)
                .join(DocumentChunkRow.document)
                .options(joinedload(DocumentChunkRow.document))
            ).scalars().all()
            chunks = [_chunk_row_to_model(row) for row in rows]
        return _rank_chunks(query, chunks, limit=limit, min_score=min_score, query_embedding=query_embedding)

    def backfill_document_embeddings(self, limit: int = 100) -> int:
        if self.embedding_service is None:
            return 0
        safe_limit = max(1, min(limit, 500))
        with self._session() as session:
            rows = session.scalars(
                select(DocumentChunkRow)
                .where(
                    (DocumentChunkRow.embedding.is_(None))
                    | (DocumentChunkRow.embedding_model != self.embedding_service.model)
                )
                .order_by(DocumentChunkRow.chunk_index)
                .limit(safe_limit)
            ).all()
            if not rows:
                return 0
            vectors = self.embedding_service.embed_texts([row.text for row in rows])
            embedded_at = datetime.now(timezone.utc)
            for row, vector in zip(rows, vectors):
                metadata = dict(row.chunk_metadata or {})
                metadata.update(
                    {
                        "has_embedding": True,
                        "embedding_model": self.embedding_service.model,
                        "embedded_at": embedded_at.isoformat(),
                    }
                )
                row.embedding = vector
                row.embedding_model = self.embedding_service.model
                row.embedded_at = embedded_at
                row.chunk_metadata = metadata
            session.commit()
            return len(vectors)

    def _session(self) -> Session:
        return self._session_factory()


def create_research_repository(config: Configuration) -> ResearchRepository:
    """Create a repository from configuration."""

    from services.embeddings import EmbeddingService

    embedding_service = EmbeddingService(config) if config.database_url and config.embedding_model else None
    if config.database_url:
        return PostgresResearchRepository(database_url=config.database_url, embedding_service=embedding_service)
    return InMemoryResearchRepository()


def _build_document(
    *,
    filename: str,
    content_type: str,
    raw_text: str,
    size_bytes: int,
    embedding_service: EmbeddingProvider | None = None,
    document_id: str | None = None,
    created_at: datetime | None = None,
) -> ResearchDocument:
    document_id = document_id or uuid4().hex
    processed_at = datetime.now(timezone.utc)
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
    chunks, embedding_error = attach_embeddings(chunks, embedding_service)
    if embedding_error:
        for chunk in chunks:
            metadata = dict(chunk.metadata)
            metadata["embedding_error"] = embedding_error
            chunk.metadata = metadata
    summary = _summarize_text(raw_text)
    return ResearchDocument(
        id=document_id,
        filename=filename,
        content_type=content_type or _content_type_for_filename(filename),
        size_bytes=size_bytes,
        raw_text=raw_text,
        summary=summary,
        status="ready",
        error_message=None,
        processed_at=processed_at,
        created_at=created_at or processed_at,
        chunks=chunks,
    )


def _content_type_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".md":
        return "text/markdown"
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
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
    query_embedding: list[float] | None = None,
) -> list[ResearchDocumentChunk]:
    query_profile = _build_query_profile(query)
    safe_limit = max(1, min(limit, 20))
    if not chunks:
        return []
    if not query_profile["terms"] and not query_profile["phrases"] and not query_embedding:
        return chunks[:safe_limit]

    avg_len = max(1.0, sum(_chunk_length(chunk) for chunk in chunks) / max(1, len(chunks)))
    bm25_scores: dict[str, tuple[float, list[str]]] = {}
    for chunk in chunks:
        bm25_scores[chunk.id] = _score_chunk(chunk, query_profile, avg_len)
    max_bm25 = max((score for score, _ in bm25_scores.values()), default=0.0)

    scored: list[tuple[float, ResearchDocumentChunk]] = []
    for chunk in chunks:
        bm25_score, matched_terms = bm25_scores[chunk.id]
        vector_score = cosine_similarity(query_embedding, chunk.embedding) if query_embedding else 0.0
        if vector_score <= 0 and bm25_score < min_score:
            continue
        if vector_score <= 0 and bm25_score <= 0:
            continue

        bm25_norm = bm25_score / max_bm25 if max_bm25 > 0 else 0.0
        hybrid_score = (0.55 * vector_score + 0.45 * bm25_norm) if query_embedding else bm25_score
        display_score = hybrid_score * 100 if query_embedding else hybrid_score
        metadata = dict(chunk.metadata)
        metadata.update(
            {
                "score": round(display_score, 4),
                "hybrid_score": round(display_score, 4),
                "bm25_score": round(bm25_score, 4),
                "vector_score": round(vector_score * 100, 4),
                "matched_terms": matched_terms,
                "snippet": _best_snippet(chunk.text, query_profile),
            }
        )
        scored.append(
            (
                hybrid_score,
                ResearchDocumentChunk(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    document_title=chunk.document_title,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    metadata=metadata,
                    embedding=chunk.embedding,
                    embedding_model=chunk.embedding_model,
                    embedded_at=chunk.embedded_at,
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
        "status": document.status,
        "error_message": document.error_message,
        "processed_at": document.processed_at.isoformat() if document.processed_at else None,
        "created_at": document.created_at.isoformat(),
        "chunk_count": len(document.chunks),
    }


def _document_to_detail(document: ResearchDocument) -> dict[str, Any]:
    return {
        **_document_to_summary(document),
        "raw_text": document.raw_text or "",
        "chunks": [_chunk_to_dict(chunk) for chunk in document.chunks] if document.status == "ready" else [],
    }


def _document_job_to_dict(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job["id"],
        "document_id": job["document_id"],
        "filename": job.get("filename"),
        "content_type": job.get("content_type"),
        "job_type": job["job_type"],
        "status": job["status"],
        "error_message": job.get("error_message"),
        "attempts": job["attempts"],
        "payload": job.get("payload"),
        "created_at": job["created_at"].isoformat() if hasattr(job["created_at"], "isoformat") else job["created_at"],
        "started_at": job.get("started_at").isoformat() if job.get("started_at") else None,
        "finished_at": job.get("finished_at").isoformat() if job.get("finished_at") else None,
    }


def _document_job_row_to_dict(row: DocumentJobRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "document_id": row.document_id,
        "filename": row.document.filename if row.document else None,
        "content_type": row.document.content_type if row.document else None,
        "job_type": row.job_type,
        "status": row.status,
        "error_message": row.error_message,
        "attempts": row.attempts,
        "payload": row.payload,
        "created_at": row.created_at.isoformat(),
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
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
        "status": row.status,
        "error_message": row.error_message,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
        "created_at": row.created_at.isoformat(),
        "chunk_count": len(row.chunks),
    }


def _document_row_to_detail(row: DocumentRow) -> dict[str, Any]:
    return {
        **_document_row_to_summary(row),
        "raw_text": row.raw_text or "",
        "chunks": [_chunk_row_to_dict(chunk) for chunk in row.chunks] if row.status == "ready" else [],
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
        embedding=row.embedding,
        embedding_model=row.embedding_model,
        embedded_at=row.embedded_at,
    )

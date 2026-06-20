"""研究数据的持久化边界。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, joinedload, sessionmaker

from config import Configuration
from models import ResearchReport, ResearchRun, ResearchSource, ResearchTask
from services.database import (
    ResearchReportRow,
    ResearchRunRow,
    ResearchSourceRow,
    ResearchTaskRow,
    create_database_engine,
    create_session_factory,
)


class ResearchRepository(Protocol):
    """研究数据存储协议。"""

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


@dataclass
class InMemoryResearchRepository:
    """未配置数据库时使用的简单内存仓库。"""

    runs: dict[str, ResearchRun] = field(default_factory=dict)
    tasks: dict[tuple[str, int], ResearchTask] = field(default_factory=dict)
    sources: list[ResearchSource] = field(default_factory=list)
    reports: dict[str, ResearchReport] = field(default_factory=dict)

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

    def _run_summary(self, run: ResearchRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "topic": run.topic,
            "search_api": run.search_api,
            "created_at": run.created_at.isoformat(),
        }


class PostgresResearchRepository:
    """使用 SQLAlchemy 同步会话保存研究历史。"""

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

    def _session(self) -> Session:
        return self._session_factory()


def create_research_repository(config: Configuration) -> ResearchRepository:
    """根据配置创建研究仓库。"""

    if config.database_url:
        return PostgresResearchRepository(database_url=config.database_url)
    return InMemoryResearchRepository()


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

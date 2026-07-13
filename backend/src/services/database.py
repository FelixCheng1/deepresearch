"""SQLAlchemy 数据库模型与连接工具。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.types import UserDefinedType


class Base(DeclarativeBase):
    """所有数据库表模型的基类。"""


class Vector1536(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "vector(1536)"

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                return value
            return "[" + ",".join(str(float(item)) for item in value) + "]"

        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None or isinstance(value, list):
                return value
            stripped = str(value).strip().strip("[]")
            if not stripped:
                return []
            return [float(item) for item in stripped.split(",")]

        return process

class ResearchRunRow(Base):
    """一次研究运行。"""

    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    search_api: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    tasks: Mapped[list[ResearchTaskRow]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ResearchTaskRow.task_id",
    )
    sources: Mapped[list[ResearchSourceRow]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ResearchSourceRow.id",
    )
    report: Mapped[ResearchReportRow | None] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
    )
    tool_calls: Mapped[list[ResearchToolCallRow]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ResearchToolCallRow.event_id",
    )


class ResearchTaskRow(Base):
    """研究任务快照。"""

    __tablename__ = "research_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[ResearchRunRow] = relationship(back_populates="tasks")


class ResearchSourceRow(Base):
    """网页或文档来源快照。"""

    __tablename__ = "research_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    run: Mapped[ResearchRunRow] = relationship(back_populates="sources")


class ResearchReportRow(Base):
    """最终报告快照。"""

    __tablename__ = "research_reports"

    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    note_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[ResearchRunRow] = relationship(back_populates="report")


class ResearchToolCallRow(Base):
    """研究运行中的结构化工具调用。"""

    __tablename__ = "research_tool_calls"
    __table_args__ = (
        UniqueConstraint("run_id", "event_id", name="uq_research_tool_calls_run_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    agent: Mapped[str] = mapped_column(String(128), nullable=False)
    tool: Mapped[str] = mapped_column(String(128), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    run: Mapped[ResearchRunRow] = relationship(back_populates="tool_calls")


class DocumentRow(Base):
    """上传到文档库的文本文件。"""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, default="text/plain")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    chunks: Mapped[list[DocumentChunkRow]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunkRow.chunk_index",
    )
    jobs: Mapped[list[DocumentJobRow]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentJobRow.created_at",
    )


class DocumentJobRow(Base):
    """Background parsing/index jobs for uploaded documents."""

    __tablename__ = "document_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, default="parse")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[DocumentRow] = relationship(back_populates="jobs")


class DocumentChunkRow(Base):
    """上传文档的文本片段。"""

    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector1536(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[DocumentRow] = relationship(back_populates="chunks")


def create_database_engine(database_url: str) -> Engine:
    """创建数据库引擎，供仓库和 Alembic 复用。"""

    return create_engine(database_url, pool_pre_ping=True, future=True)


def create_session_factory(engine: Engine) -> sessionmaker:
    """创建每次操作独立使用的 session 工厂。"""

    return sessionmaker(bind=engine, expire_on_commit=False, future=True)

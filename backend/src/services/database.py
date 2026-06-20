"""SQLAlchemy 数据库模型与连接工具。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    """所有数据库表模型的基类。"""


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
    note_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[ResearchRunRow] = relationship(back_populates="tasks")


class ResearchSourceRow(Base):
    """网页来源快照。"""

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


def create_database_engine(database_url: str) -> Engine:
    """创建数据库引擎，供仓库和 Alembic 复用。"""

    return create_engine(database_url, pool_pre_ping=True, future=True)


def create_session_factory(engine: Engine) -> sessionmaker:
    """创建每次操作独立使用的 session 工厂。"""

    return sessionmaker(bind=engine, expire_on_commit=False, future=True)

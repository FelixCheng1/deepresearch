"""创建研究历史表

Revision ID: 20260620_0001
Revises:
Create Date: 2026-06-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260620_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建研究历史相关表。"""

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "research_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("search_api", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "research_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note_id", sa.String(length=128), nullable=True),
        sa.Column("note_path", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "task_id", name="uq_research_tasks_run_task"),
    )
    op.create_index("ix_research_tasks_run_id", "research_tasks", ["run_id"])

    op.create_table(
        "research_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_research_sources_run_id", "research_sources", ["run_id"])

    op.create_table(
        "research_reports",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("note_id", sa.String(length=128), nullable=True),
        sa.Column("note_path", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    """删除研究历史相关表。"""

    op.drop_table("research_reports")
    op.drop_index("ix_research_sources_run_id", table_name="research_sources")
    op.drop_table("research_sources")
    op.drop_index("ix_research_tasks_run_id", table_name="research_tasks")
    op.drop_table("research_tasks")
    op.drop_table("research_runs")

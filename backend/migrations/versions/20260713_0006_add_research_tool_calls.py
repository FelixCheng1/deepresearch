"""add structured research tool call history

Revision ID: 20260713_0006
Revises: 20260620_0005
Create Date: 2026-07-13 00:06:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260713_0006"
down_revision = "20260620_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_tool_calls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("agent", sa.String(length=128), nullable=False),
        sa.Column("tool", sa.String(length=128), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False, server_default=""),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("note_id", sa.String(length=128), nullable=True),
        sa.Column("step", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "event_id", name="uq_research_tool_calls_run_event"),
    )
    op.create_index("ix_research_tool_calls_run_id", "research_tool_calls", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_research_tool_calls_run_id", table_name="research_tool_calls")
    op.drop_table("research_tool_calls")

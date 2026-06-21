"""add document jobs

Revision ID: 20260620_0005
Revises: 20260620_0004
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260620_0005"
down_revision = "20260620_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("document_id", sa.String(length=64), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False, server_default="parse"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_document_jobs_document_id", "document_jobs", ["document_id"])
    op.create_index("ix_document_jobs_status", "document_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_document_jobs_status", table_name="document_jobs")
    op.drop_index("ix_document_jobs_document_id", table_name="document_jobs")
    op.drop_table("document_jobs")

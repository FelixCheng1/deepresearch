"""add document processing status

Revision ID: 20260620_0004
Revises: 20260620_0003
Create Date: 2026-06-20 00:04:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260620_0004"
down_revision = "20260620_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"))
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("documents", "raw_text", existing_type=sa.Text(), nullable=True)
    op.execute("UPDATE documents SET status = 'ready' WHERE status IS NULL")
    op.execute("UPDATE documents SET processed_at = created_at WHERE processed_at IS NULL AND raw_text IS NOT NULL")
    op.alter_column("documents", "status", server_default=None)


def downgrade() -> None:
    op.alter_column("documents", "raw_text", existing_type=sa.Text(), nullable=False)
    op.drop_column("documents", "processed_at")
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "status")

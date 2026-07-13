"""persist research task summaries for history replay

Revision ID: 20260713_0007
Revises: 20260713_0006
Create Date: 2026-07-13 00:07:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260713_0007"
down_revision = "20260713_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("research_tasks", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("research_tasks", sa.Column("sources_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("research_tasks", "sources_summary")
    op.drop_column("research_tasks", "summary")

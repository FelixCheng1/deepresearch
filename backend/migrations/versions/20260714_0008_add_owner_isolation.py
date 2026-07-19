"""add owner isolation

Revision ID: 20260714_0008
Revises: 20260713_0007
"""

import sqlalchemy as sa
from alembic import op

revision = "20260714_0008"
down_revision = "20260713_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("research_runs", sa.Column("owner_id", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("owner_id", sa.String(length=64), nullable=True))
    op.execute("UPDATE research_runs SET owner_id = 'legacy' WHERE owner_id IS NULL")
    op.execute("UPDATE documents SET owner_id = 'legacy' WHERE owner_id IS NULL")
    op.alter_column("research_runs", "owner_id", nullable=False)
    op.alter_column("documents", "owner_id", nullable=False)
    op.create_index("ix_research_runs_owner_id", "research_runs", ["owner_id"])
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_owner_id", table_name="documents")
    op.drop_index("ix_research_runs_owner_id", table_name="research_runs")
    op.drop_column("documents", "owner_id")
    op.drop_column("research_runs", "owner_id")

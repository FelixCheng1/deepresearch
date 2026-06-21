"""add document chunk embeddings

Revision ID: 20260620_0003
Revises: 20260620_0002
Create Date: 2026-06-20 00:03:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260620_0003"
down_revision = "20260620_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(1536)")
    op.add_column("document_chunks", sa.Column("embedding_model", sa.String(length=128), nullable=True))
    op.add_column("document_chunks", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        DO $$
        BEGIN
            BEGIN
                CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
                ON document_chunks USING hnsw (embedding vector_cosine_ops)
                WHERE embedding IS NOT NULL;
            EXCEPTION WHEN undefined_object OR feature_not_supported OR invalid_parameter_value THEN
                BEGIN
                    CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_ivfflat
                    ON document_chunks USING ivfflat (embedding vector_cosine_ops)
                    WHERE embedding IS NOT NULL;
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'pgvector index creation skipped: %', SQLERRM;
                END;
            END;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_ivfflat")
    op.drop_column("document_chunks", "embedded_at")
    op.drop_column("document_chunks", "embedding_model")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")

"""Persist whole-publication MedCPT embeddings with pgvector."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

revision = "20261006_01"
down_revision = "20261001_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "unit_embeddings",
        sa.Column("unit_id", sa.String(64), primary_key=True),
        sa.Column("publication_id", sa.Uuid(), sa.ForeignKey("publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("strategy", sa.String(64), nullable=False),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_title", sa.Text(), nullable=False),
        sa.Column("source_abstract", sa.Text()),
        sa.Column("configuration", JSONB(), nullable=False),
        sa.Column("vector", Vector(768), nullable=False),
        sa.UniqueConstraint("publication_id", name="uq_unit_embeddings_publication"),
    )


def downgrade() -> None:
    op.drop_table("unit_embeddings")
    # Extension may be shared by other applications/tables; retain it.

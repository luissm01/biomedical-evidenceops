"""PostgreSQL-backed queue for asynchronous PubMed ingestion (M11.1, D036)."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261113_01"
down_revision = "20261006_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("search_limit", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("worker_id", sa.String(128)),
        sa.Column("last_error", sa.String(128)),
        sa.Column("result", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("idempotency_key", name="uq_ingestion_jobs_idempotency_key"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')", name="ck_ingestion_jobs_status",
        ),
        sa.CheckConstraint("search_limit BETWEEN 1 AND 100", name="ck_ingestion_jobs_search_limit"),
        sa.CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="ck_ingestion_jobs_attempts"),
        sa.CheckConstraint(
            "(status = 'running') = (lease_expires_at IS NOT NULL)",
            name="ck_ingestion_jobs_running_lease",
        ),
    )
    op.create_index(
        "ix_ingestion_jobs_queued_run_after", "ingestion_jobs", ["run_after"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "ix_ingestion_jobs_running_lease", "ingestion_jobs", ["lease_expires_at"],
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_jobs")

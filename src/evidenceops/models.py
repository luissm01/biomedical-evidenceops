from uuid import UUID
from datetime import datetime

from pgvector.sqlalchemy import Vector

from sqlalchemy import (
    CheckConstraint, ForeignKey, DateTime, Index, Integer, String, Text, UniqueConstraint, Uuid,
    func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    text: Mapped[str] = mapped_column(String(2000))


class Publication(Base):
    __tablename__ = "publications"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_publications_source_source_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    authors: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    journal: Mapped[str | None] = mapped_column(Text)
    doi: Mapped[str | None] = mapped_column(Text)
    publication_year: Mapped[int | None] = mapped_column(Integer)
    source_url: Mapped[str | None] = mapped_column(Text)
    first_ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UnitEmbedding(Base):
    __tablename__ = "unit_embeddings"
    __table_args__ = (UniqueConstraint("publication_id", name="uq_unit_embeddings_publication"),)

    unit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    publication_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("publications.id", ondelete="CASCADE"), nullable=False
    )
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Source snapshot for excluding stale rows even before explicit reindexing.
    source_title: Mapped[str] = mapped_column(Text, nullable=False)
    source_abstract: Mapped[str | None] = mapped_column(Text)
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)


class IngestionJob(Base):
    """One queued PubMed ingestion request; PostgreSQL is the queue (D036)."""

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ingestion_jobs_idempotency_key"),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_ingestion_jobs_status",
        ),
        CheckConstraint("search_limit BETWEEN 1 AND 100", name="ck_ingestion_jobs_search_limit"),
        CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="ck_ingestion_jobs_attempts"),
        CheckConstraint(
            "(status = 'running') = (lease_expires_at IS NOT NULL)",
            name="ck_ingestion_jobs_running_lease",
        ),
        # Claim scans only claimable rows: due queued jobs and expired leases.
        Index("ix_ingestion_jobs_queued_run_after", "run_after",
              postgresql_where=text("status = 'queued'")),
        Index("ix_ingestion_jobs_running_lease", "lease_expires_at",
              postgresql_where=text("status = 'running'")),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    search_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(128))
    last_error: Mapped[str | None] = mapped_column(String(128))
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

from uuid import UUID
from datetime import datetime

from pgvector.sqlalchemy import Vector

from sqlalchemy import ForeignKey, DateTime, Integer, String, Text, UniqueConstraint, Uuid, func
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

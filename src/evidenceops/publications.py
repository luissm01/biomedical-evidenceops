"""Atomic PostgreSQL persistence for normalized biomedical documents."""

from uuid import uuid4

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from evidenceops.biomedical import BiomedicalDocument
from evidenceops.models import Publication


def as_biomedical_document(publication: Publication) -> BiomedicalDocument:
    """Copy persisted bibliographic fields back into the domain contract."""
    return BiomedicalDocument(
        source=publication.source,
        source_id=publication.source_id,
        title=publication.title,
        abstract=publication.abstract,
        authors=list(publication.authors),
        journal=publication.journal,
        doi=publication.doi,
        publication_year=publication.publication_year,
        source_url=publication.source_url,
    )


def upsert_publication(session: Session, document: BiomedicalDocument) -> Publication:
    """Write one document in the caller's transaction; never commit here.

    The conflict target is the external identity. A new UUID is ignored on
    conflict, preserving the existing row and its first ingestion timestamp.
    """
    values = {
        "id": uuid4(),
        "source": document.source,
        "source_id": document.source_id,
        "title": document.title,
        "abstract": document.abstract,
        "authors": list(document.authors),
        "journal": document.journal,
        "doi": document.doi,
        "publication_year": document.publication_year,
        "source_url": document.source_url,
    }
    statement = insert(Publication).values(**values)
    statement = statement.on_conflict_do_update(
        constraint="uq_publications_source_source_id",
        set_={
            column: getattr(statement.excluded, column)
            for column in (
                "title", "abstract", "authors", "journal", "doi",
                "publication_year", "source_url",
            )
        } | {"last_ingested_at": func.clock_timestamp()},
    ).returning(Publication)
    return session.scalars(statement, execution_options={"populate_existing": True}).one()

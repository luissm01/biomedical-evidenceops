from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from evidenceops.biomedical import BiomedicalDocument
from evidenceops.config import Settings
from evidenceops.database import create_database
from evidenceops.models import Publication
from evidenceops.publications import as_biomedical_document, upsert_publication


@pytest.fixture
def publication_sessions(
    test_settings: Settings, migrated_database: None
) -> Iterator[sessionmaker[Session]]:
    engine, factory = create_database(test_settings)
    with factory.begin() as session:
        session.execute(delete(Publication))
    try:
        yield factory
    finally:
        with factory.begin() as session:
            session.execute(delete(Publication))
        engine.dispose()


@pytest.fixture
def document() -> BiomedicalDocument:
    return BiomedicalDocument(
        source="pubmed",
        source_id="12345",
        title="Original title",
        abstract="BACKGROUND: Initial abstract.",
        authors=["Ada Example", "Study Group"],
        journal="Journal of Evidence",
        doi="10.1234/example",
        publication_year=2024,
        source_url="https://pubmed.ncbi.nlm.nih.gov/12345/",
    )


def test_insert_persists_complete_contract_and_jsonb(
    publication_sessions: sessionmaker[Session], document: BiomedicalDocument
) -> None:
    with publication_sessions.begin() as session:
        created = upsert_publication(session, document)
        publication_id = created.id
        first = created.first_ingested_at
        last = created.last_ingested_at

    assert isinstance(publication_id, UUID) and publication_id.version == 4
    assert first.tzinfo is not None and first.utcoffset() == timedelta(0)
    assert last.tzinfo is not None and last.utcoffset() == timedelta(0)
    with publication_sessions() as session:
        persisted = session.get(Publication, publication_id)
        assert persisted is not None
        assert as_biomedical_document(persisted) == document
        assert session.scalar(text("SELECT pg_typeof(authors)::text FROM publications WHERE id = :id"), {"id": publication_id}) == "jsonb"
        converted = as_biomedical_document(persisted)
        converted.authors.append("Only in copy")
        assert persisted.authors == document.authors


def test_reingestion_updates_metadata_and_last_timestamp_without_new_row(
    publication_sessions: sessionmaker[Session], document: BiomedicalDocument
) -> None:
    with publication_sessions.begin() as session:
        original = upsert_publication(session, document)
        publication_id = original.id
        first = original.first_ingested_at

    old_last = datetime(2000, 1, 1, tzinfo=timezone.utc)
    with publication_sessions.begin() as session:
        session.execute(update(Publication).where(Publication.id == publication_id).values(last_ingested_at=old_last))

    revised = replace(
        document, title="Updated title", abstract=None, authors=["Revised Group"],
        journal=None, doi=None, publication_year=None, source_url=None,
    )
    with publication_sessions.begin() as session:
        updated = upsert_publication(session, revised)
        assert updated.id == publication_id
        assert updated.first_ingested_at == first
        assert updated.last_ingested_at > old_last

    with publication_sessions() as session:
        assert session.scalar(select(func.count()).select_from(Publication)) == 1
        persisted = session.get(Publication, publication_id)
        assert persisted is not None
        assert as_biomedical_document(persisted) == revised
        assert persisted.first_ingested_at == first
        assert persisted.last_ingested_at > old_last


def test_source_and_source_id_define_identity_not_doi(
    publication_sessions: sessionmaker[Session], document: BiomedicalDocument
) -> None:
    with publication_sessions.begin() as session:
        one = upsert_publication(session, document)
        two = upsert_publication(session, replace(document, source="other_source"))
        three = upsert_publication(session, replace(document, source_id="67890"))
    assert len({one.id, two.id, three.id}) == 3
    with publication_sessions() as session:
        assert session.scalar(select(func.count()).select_from(Publication)) == 3


def test_upsert_refreshes_loaded_row_in_same_transaction(
    publication_sessions: sessionmaker[Session], document: BiomedicalDocument
) -> None:
    with publication_sessions.begin() as session:
        first = upsert_publication(session, document)
        second = upsert_publication(session, replace(document, title="Second title"))
        assert second.id == first.id
        assert first.title == second.title == "Second title"
        assert first.first_ingested_at == second.first_ingested_at
    with publication_sessions() as session:
        assert session.scalar(select(func.count()).select_from(Publication)) == 1


def test_unique_constraint_rejects_duplicate_external_identity(
    publication_sessions: sessionmaker[Session], document: BiomedicalDocument
) -> None:
    with publication_sessions.begin() as session:
        upsert_publication(session, document)

    with pytest.raises(IntegrityError):
        with publication_sessions.begin() as session:
            session.execute(insert(Publication).values(
                id=uuid4(), source=document.source, source_id=document.source_id,
                title="Duplicate", authors=[],
            ))
    with publication_sessions() as session:
        assert session.scalar(select(func.count()).select_from(Publication)) == 1


def test_caller_transaction_rolls_back_upsert_on_later_failure(
    publication_sessions: sessionmaker[Session], document: BiomedicalDocument
) -> None:
    with publication_sessions.begin() as session:
        initial = upsert_publication(session, document)
        original_first = initial.first_ingested_at
        original_last = initial.last_ingested_at

    with pytest.raises(IntegrityError):
        with publication_sessions.begin() as session:
            upsert_publication(session, replace(document, title="Should roll back"))
            session.execute(insert(Publication).values(
                id=uuid4(), source=document.source, source_id=document.source_id,
                title="Duplicate", authors=[],
            ))

    with publication_sessions() as session:
        persisted = session.scalar(select(Publication))
        assert persisted is not None
        assert as_biomedical_document(persisted) == document
        assert persisted.first_ingested_at == original_first
        assert persisted.last_ingested_at == original_last
        assert session.scalar(select(func.count()).select_from(Publication)) == 1

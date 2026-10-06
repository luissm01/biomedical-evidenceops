from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from evidenceops.biomedical import BiomedicalDocument
from evidenceops.database import create_database
from evidenceops.embeddings import EmbeddingCompatibilityError, MedCPTConfig, validate_vector
from evidenceops.models import Publication, UnitEmbedding
from evidenceops.publications import upsert_publication
from evidenceops.retrieval import index_publication, search


def vector(*values):
    return list(values) + [0.0] * (768 - len(values))


class ControlledMedCPT:
    config = MedCPTConfig()

    def __init__(self):
        self.article_calls = []
        self.query_calls = []
        self.vectors = {}
        self.query_vector = vector(1, 0)

    def encode_article(self, unit):
        self.article_calls.append(unit)
        return self.vectors.get(unit.source_id, vector(1, 0))

    def encode_query(self, query):
        self.query_calls.append(query)
        return self.query_vector


@pytest.fixture
def sessions(test_settings, migrated_database):
    engine, factory = create_database(test_settings)
    with factory.begin() as session:
        session.execute(delete(Publication))
    try:
        yield factory
    finally:
        with factory.begin() as session:
            session.execute(delete(Publication))
        engine.dispose()


def document(source_id="1", year=2024, title="Diabetes", abstract="Treatment evidence"):
    return BiomedicalDocument(source="pubmed", source_id=source_id, title=title,
        abstract=abstract, authors=["Study Group"], journal="Evidence", doi="10.1/test",
        publication_year=year, source_url=f"https://pubmed.ncbi.nlm.nih.gov/{source_id}/")


def persist(sessions, doc):
    with sessions.begin() as session:
        return upsert_publication(session, doc).id


def test_persistence_idempotence_and_content_reindex(sessions):
    encoder = ControlledMedCPT()
    doc = document()
    publication_id = persist(sessions, doc)
    assert index_publication(sessions, publication_id, encoder) == "indexed"
    assert index_publication(sessions, publication_id, encoder) == "unchanged"
    assert len(encoder.article_calls) == 1
    with sessions() as session:
        row = session.scalar(select(UnitEmbedding))
        unit_id, fingerprint = row.unit_id, row.content_fingerprint
        assert row.configuration == encoder.config.metadata()
        assert row.publication_id == publication_id
        assert list(row.vector) == vector(1, 0)
    persist(sessions, replace(doc, abstract="Updated evidence"))
    assert search(sessions, encoder, query="diabetes", top_k=3) == []
    encoder.vectors["1"] = vector(3, 0)
    assert index_publication(sessions, publication_id, encoder) == "indexed"
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(UnitEmbedding)) == 1
        row = session.scalar(select(UnitEmbedding))
        assert row.unit_id == unit_id and row.content_fingerprint != fingerprint
    result = search(sessions, encoder, query="diabetes", top_k=3)[0]
    assert result.score == 3
    assert result.unit.abstract == "Updated evidence"
    assert result.unit.source_id == "1" and result.unit.authors == ("Study Group",)


def test_dot_product_ranking_filters_ties_and_provenance(sessions):
    encoder = ControlledMedCPT()
    # Cosine would rank (1,0) above (3,100); dot product must do the reverse.
    encoder.vectors = {"1": vector(1, 0), "2": vector(3, 100), "3": vector(3, 0), "4": vector(-1, 0)}
    for source_id, year in [("1", 2024), ("2", 2019), ("3", None), ("4", 2020)]:
        index_publication(sessions, persist(sessions, document(source_id, year)), encoder)
    results = search(sessions, encoder, query="  diabetes  ", top_k=10)
    assert [r.score for r in results] == [3, 3, 1, -1]
    assert [r.unit.unit_id for r in results[:2]] == sorted(r.unit.unit_id for r in results[:2])
    assert encoder.query_calls[-1] == "diabetes"
    assert [r.unit.source_id for r in search(sessions, encoder, query="x", top_k=2, published_from=2020)] == ["1", "4"]
    assert search(sessions, encoder, query="x", top_k=2, published_from=2025) == []
    assert len(search(sessions, encoder, query="x", top_k=1)) == 1
    assert results[0].unit.text and results[0].unit.source_url


def test_metadata_updates_do_not_reencode_and_filter_uses_current_year(sessions):
    encoder = ControlledMedCPT()
    doc = document(year=2019)
    publication_id = persist(sessions, doc)
    index_publication(sessions, publication_id, encoder)
    persist(sessions, replace(doc, publication_year=2024, authors=["New author"]))
    assert index_publication(sessions, publication_id, encoder) == "unchanged"
    assert len(encoder.article_calls) == 1
    result = search(sessions, encoder, query="x", top_k=1, published_from=2020)[0]
    assert result.unit.authors == ("New author",)


def test_empty_and_removed_content_and_cascade(sessions):
    encoder = ControlledMedCPT()
    assert search(sessions, encoder, query="x", top_k=10) == []
    doc = document()
    publication_id = persist(sessions, doc)
    index_publication(sessions, publication_id, encoder)
    persist(sessions, replace(doc, title=" ", abstract=None))
    assert search(sessions, encoder, query="x", top_k=10) == []
    assert index_publication(sessions, publication_id, encoder) == "omitted"
    assert len(encoder.article_calls) == 1
    persist(sessions, doc)
    index_publication(sessions, publication_id, encoder)
    with sessions.begin() as session:
        session.execute(delete(Publication))
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(UnitEmbedding)) == 0


@pytest.mark.parametrize("change", [dict(article_revision="different"), dict(query_model="different"), dict(encoding="different"), dict(query_max_tokens=32), dict(overflow="reject")])
def test_incompatible_configuration_requires_explicit_rebuild(sessions, change):
    encoder = ControlledMedCPT()
    publication_id = persist(sessions, document())
    index_publication(sessions, publication_id, encoder)
    encoder.config = replace(encoder.config, **change)
    with pytest.raises(EmbeddingCompatibilityError):
        index_publication(sessions, publication_id, encoder)
    with pytest.raises(EmbeddingCompatibilityError):
        search(sessions, encoder, query="x", top_k=1)
    assert len(encoder.article_calls) == 1
    index_publication(sessions, publication_id, encoder, replace_incompatible=True)
    assert len(search(sessions, encoder, query="x", top_k=1)) == 1


def test_dimension_and_invalid_output_leave_existing_embedding(sessions):
    encoder = ControlledMedCPT()
    publication_id = persist(sessions, document())
    index_publication(sessions, publication_id, encoder)
    persist(sessions, document(title="Changed"))
    encoder.vectors["1"] = [1, 0]
    with pytest.raises(EmbeddingCompatibilityError):
        index_publication(sessions, publication_id, encoder)
    with sessions() as session:
        assert session.scalar(select(UnitEmbedding)).source_title == "Diabetes"
    encoder.query_vector = [1, 0]
    with pytest.raises(EmbeddingCompatibilityError):
        search(sessions, encoder, query="x", top_k=1)
    encoder.config = replace(encoder.config, dimensions=2)
    with pytest.raises(EmbeddingCompatibilityError):
        index_publication(sessions, publication_id, encoder)


def test_source_change_during_encoding_is_not_persisted(sessions):
    encoder = ControlledMedCPT()
    doc = document()
    publication_id = persist(sessions, doc)
    original = encoder.encode_article
    def changing(unit):
        persist(sessions, replace(doc, title="Concurrent change"))
        return original(unit)
    encoder.encode_article = changing
    with pytest.raises(RuntimeError, match="changed"):
        index_publication(sessions, publication_id, encoder)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(UnitEmbedding)) == 0


@pytest.mark.parametrize("top_k", [0, -1, True, 1.5, "2", None])
def test_invalid_top_k_before_model_or_db(top_k):
    encoder = ControlledMedCPT()
    with pytest.raises(ValueError, match="top_k"):
        search(None, encoder, query="x", top_k=top_k)
    assert encoder.query_calls == []


@pytest.mark.parametrize("query", ["", "  ", None])
def test_invalid_query_before_model_or_db(query):
    with pytest.raises(ValueError, match="Query"):
        search(None, ControlledMedCPT(), query=query, top_k=1)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1e39])
def test_nonfinite_or_overflow_vector(value):
    with pytest.raises(ValueError, match="finite"):
        validate_vector(vector(value))


def test_same_joined_text_with_changed_encoder_pair_is_reencoded(sessions):
    encoder = ControlledMedCPT()
    doc = document(title="Title\n\nAbstract", abstract=None)
    publication_id = persist(sessions, doc)
    index_publication(sessions, publication_id, encoder)
    initial_unit = encoder.article_calls[0]
    persist(sessions, replace(doc, title="Title", abstract="Abstract"))
    assert index_publication(sessions, publication_id, encoder) == "indexed"
    assert len(encoder.article_calls) == 2
    assert encoder.article_calls[1].content_fingerprint == initial_unit.content_fingerprint


def test_blank_source_field_changes_reuse_equivalent_model_input(sessions):
    encoder = ControlledMedCPT()
    doc = document(abstract=None)
    publication_id = persist(sessions, doc)
    index_publication(sessions, publication_id, encoder)
    persist(sessions, replace(doc, abstract="  "))
    assert index_publication(sessions, publication_id, encoder) == "unchanged"
    assert len(encoder.article_calls) == 1
    assert len(search(sessions, encoder, query="x", top_k=1)) == 1


def test_mixed_corpus_is_rejected_even_when_filter_excludes_incompatible_row(sessions):
    encoder = ControlledMedCPT()
    one = persist(sessions, document("1", 2024))
    two = persist(sessions, document("2", 2019))
    index_publication(sessions, one, encoder)
    index_publication(sessions, two, encoder)
    encoder.config = replace(encoder.config, article_revision="new")
    index_publication(sessions, one, encoder, replace_incompatible=True)
    with pytest.raises(EmbeddingCompatibilityError):
        search(sessions, encoder, query="x", top_k=1, published_from=2020)
    index_publication(sessions, two, encoder, replace_incompatible=True)
    assert len(search(sessions, encoder, query="x", top_k=10)) == 2


@pytest.mark.parametrize("year", [0, -1, True, "2020", 2020.5])
def test_invalid_filter_before_model_or_db(year):
    encoder = ControlledMedCPT()
    with pytest.raises(ValueError, match="published_from"):
        search(None, encoder, query="x", top_k=1, published_from=year)
    assert encoder.query_calls == []


def test_missing_publication_before_encoding(sessions):
    encoder = ControlledMedCPT()
    with pytest.raises(ValueError, match="does not exist"):
        index_publication(sessions, uuid4(), encoder)
    assert encoder.article_calls == []

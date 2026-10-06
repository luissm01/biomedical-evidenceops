from dataclasses import FrozenInstanceError, replace
from uuid import UUID

import pytest

from evidenceops import chunking
from evidenceops.biomedical import BiomedicalDocument
from evidenceops.chunking import build_retrievable_unit


PUBLICATION_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def document() -> BiomedicalDocument:
    return BiomedicalDocument(
        source="pubmed", source_id="12345", title="Original title",
        abstract="BACKGROUND: Initial abstract.", authors=["Ada Example"],
        journal="Journal of Evidence", doi="10.1234/example",
        publication_year=2024, source_url="https://pubmed.ncbi.nlm.nih.gov/12345/",
    )


def test_normal_publication_preserves_content_and_provenance(document):
    unit = build_retrievable_unit(document, publication_id=PUBLICATION_ID)

    assert unit is not None
    assert unit.publication_id == PUBLICATION_ID
    assert (unit.source, unit.source_id) == ("pubmed", "12345")
    assert unit.strategy == "whole-publication-v1"
    assert unit.chunk_index == 0
    assert unit.title == document.title
    assert unit.abstract == document.abstract
    assert unit.text == "Original title\n\nBACKGROUND: Initial abstract."
    assert unit.authors == ("Ada Example",)
    assert unit.journal == document.journal
    assert unit.doi == document.doi
    assert unit.publication_year == document.publication_year
    assert unit.source_url == document.source_url


@pytest.mark.parametrize("abstract", [None, "", " \t\n\u2003"])
def test_missing_or_blank_abstract_uses_only_title(document, abstract):
    unit = build_retrievable_unit(
        replace(document, abstract=abstract), publication_id=PUBLICATION_ID,
    )
    assert unit is not None
    assert unit.text == document.title
    assert unit.abstract is None


@pytest.mark.parametrize("title,abstract,expected", [
    ("A", "B", "A\n\nB"),
    ("A", None, "A"),
    ("", "B", "B"),
    ("  αβ 🧬\ne\u0301  ", " Résumé\n結果\t", "  αβ 🧬\ne\u0301  \n\n Résumé\n結果\t"),
    ("Title", "x" * 20000, "Title\n\n" + "x" * 20000),
])
def test_short_unicode_and_long_text_are_preserved(document, title, abstract, expected):
    unit = build_retrievable_unit(
        replace(document, title=title, abstract=abstract), publication_id=PUBLICATION_ID,
    )
    assert unit is not None
    assert unit.text == expected
    assert unit.title == title
    assert unit.abstract == abstract
    assert unit.chunk_index == 0


@pytest.mark.parametrize("title", ["", " \t\n\u2003"])
def test_missing_or_blank_title_uses_only_abstract(document, title):
    abstract = "  Contenido del abstract\n🧬  "
    unit = build_retrievable_unit(
        replace(document, title=title, abstract=abstract), publication_id=PUBLICATION_ID,
    )
    assert unit is not None
    assert unit.text == abstract
    assert unit.title == title
    assert unit.abstract == abstract


@pytest.mark.parametrize("title,abstract", [("", None), ("", ""), (" \t\n", "\u2003\n")])
def test_empty_publication_has_no_retrievable_unit(document, title, abstract):
    assert build_retrievable_unit(
        replace(document, title=title, abstract=abstract), publication_id=PUBLICATION_ID,
    ) is None


def test_repeated_input_has_identical_unit_and_pinned_hashes(document):
    first = build_retrievable_unit(document, publication_id=PUBLICATION_ID)
    second = build_retrievable_unit(replace(document), publication_id=PUBLICATION_ID)
    assert first == second
    assert first is not None
    assert first.unit_id == "8da2c58259c88bb3eeba1da3ebde5c73d9c87ee14ad5e39e6fbf43b0ab04780c"
    assert first.content_fingerprint == "66e819a4f3e16ba4d7450158fcc6d9e3160806097490381a0791e4d5adc7223b"


@pytest.mark.parametrize("changes", [
    {"title": "Revised title"}, {"abstract": "Revised abstract"}, {"abstract": None},
    {"title": "Original title "},
])
def test_content_change_keeps_identity_and_changes_fingerprint(document, changes):
    first = build_retrievable_unit(document, publication_id=PUBLICATION_ID)
    revised = build_retrievable_unit(replace(document, **changes), publication_id=PUBLICATION_ID)
    assert first is not None and revised is not None
    assert revised.unit_id == first.unit_id
    assert revised.content_fingerprint != first.content_fingerprint


def test_metadata_change_does_not_change_identity_or_content_fingerprint(document):
    first = build_retrievable_unit(document, publication_id=PUBLICATION_ID)
    revised = build_retrievable_unit(
        replace(document, authors=[], journal=None, doi=None, publication_year=None, source_url=None),
        publication_id=UUID("00000000-0000-0000-0000-000000000002"),
    )
    assert first is not None and revised is not None
    assert revised.unit_id == first.unit_id
    assert revised.content_fingerprint == first.content_fingerprint
    assert revised.publication_id != first.publication_id
    assert revised.authors == ()
    assert revised.source_url is None


@pytest.mark.parametrize("changes", [{"source": "other"}, {"source_id": "67890"}])
def test_source_identity_change_creates_different_unit(document, changes):
    first = build_retrievable_unit(document, publication_id=PUBLICATION_ID)
    revised = build_retrievable_unit(replace(document, **changes), publication_id=PUBLICATION_ID)
    assert first is not None and revised is not None
    assert revised.unit_id != first.unit_id
    assert revised.content_fingerprint == first.content_fingerprint


def test_identity_serialization_does_not_confuse_field_boundaries(document):
    first = build_retrievable_unit(replace(document, source="a:b", source_id="c"), publication_id=PUBLICATION_ID)
    second = build_retrievable_unit(replace(document, source="a", source_id="b:c"), publication_id=PUBLICATION_ID)
    assert first is not None and second is not None
    assert first.unit_id != second.unit_id


def test_strategy_revision_changes_identity_even_when_content_is_unchanged(document, monkeypatch):
    first = build_retrievable_unit(document, publication_id=PUBLICATION_ID)
    # Simulate a future code revision; v1 exposes no arbitrary strategy selector.
    monkeypatch.setattr(chunking, "CHUNKING_STRATEGY", "whole-publication-v2")
    revised = build_retrievable_unit(document, publication_id=PUBLICATION_ID)
    assert first is not None and revised is not None
    assert revised.strategy == "whole-publication-v2"
    assert revised.unit_id != first.unit_id
    assert revised.content_fingerprint == first.content_fingerprint


def test_unicode_fingerprint_preserves_code_points(document):
    composed = build_retrievable_unit(
        replace(document, title="é", abstract=None), publication_id=PUBLICATION_ID,
    )
    decomposed = build_retrievable_unit(
        replace(document, title="e\u0301", abstract=None), publication_id=PUBLICATION_ID,
    )
    assert composed is not None and decomposed is not None
    assert composed.content_fingerprint == "4a99557e4033c3539de2eb65472017cad5f9557f7a0625a09f1c3f6e2ba69c4c"
    assert composed.unit_id == decomposed.unit_id
    assert composed.content_fingerprint != decomposed.content_fingerprint


@pytest.mark.parametrize("changes", [{"source": ""}, {"source_id": " \t"}])
def test_missing_source_identity_is_rejected(document, changes):
    with pytest.raises(ValueError, match="source and source_id"):
        build_retrievable_unit(replace(document, **changes), publication_id=PUBLICATION_ID)


def test_unit_is_immutable_and_does_not_share_mutable_authors(document):
    unit = build_retrievable_unit(document, publication_id=PUBLICATION_ID)
    assert unit is not None
    document.authors.append("Later author")
    assert unit.authors == ("Ada Example",)
    with pytest.raises(FrozenInstanceError):
        unit.text = "Changed"

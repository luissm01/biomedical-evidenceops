import math
from uuid import UUID

import pytest

from evidenceops.biomedical import BiomedicalDocument
from evidenceops.chunking import build_retrievable_unit
from evidenceops.lexical import bm25, reciprocal_rank_fusion, tokenize


def unit(identity, text):
    return build_retrievable_unit(BiomedicalDocument(
        source="pubmed", source_id=identity, title=text, abstract=None,
        authors=[], journal=None, doi=None, publication_year=None,
        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{identity}/",
    ), publication_id=UUID(int=int(identity) + 1))


def test_tokenization():
    assert tokenize("IL-6 COVID_19, β-Cell STRASSE Straße café 2024") == [
        "il", "6", "covid", "19", "β", "cell", "strasse", "strasse", "café", "2024"]


def test_bm25_known_formula_tf_idf_length_and_query_terms():
    a, b, c = unit("1", "alpha alpha beta"), unit("2", "alpha"), unit("3", "gamma gamma")
    ranking = bm25([a, b, c], "alpha alpha")
    scores = {u.unit_id: score for u, score in ranking}
    idf = math.log1p(1.5 / 2.5)
    assert scores[a.unit_id] == pytest.approx(idf * 2 * 2.2 / (2 + 1.2 * (.25 + .75 * 3 / 2)))
    assert scores[b.unit_id] == pytest.approx(idf * 2.2 / (1 + 1.2 * (.25 + .75 / 2)))
    assert ranking == bm25([c, b, a], "alpha")
    assert len(ranking) == 2
    assert bm25([a, b, c], "gamma")[0][1] > scores[b.unit_id]
    assert bm25([], "alpha") == []
    assert bm25([a], "unknown") == []
    assert bm25([a], "---") == []
    assert bm25([unit("4", "!!!")], "alpha") == []


def test_bm25_ties():
    units = [unit("1", "alpha"), unit("2", "alpha")]
    ranking = bm25(units, "alpha")
    assert [u.unit_id for u, _ in ranking] == sorted(u.unit_id for u in units)


def test_rrf_scores_deduplication_ties_and_missing_candidates():
    a, b, c = [unit(str(i), "alpha") for i in range(3)]
    rankings = [[(a, 999), (a, 999), (b, -5)], [(b, .1), (a, .01), (c, 0)]]
    result = reciprocal_rank_fusion(rankings)
    scores = {u.unit_id: score for u, score in result}
    assert scores[a.unit_id] == scores[b.unit_id] == 1/61 + 1/62
    assert scores[c.unit_id] == 1/63
    assert [u.unit_id for u, _ in result[:2]] == sorted([a.unit_id, b.unit_id])
    assert result == reciprocal_rank_fusion(rankings[::-1])
    assert reciprocal_rank_fusion([[], []]) == []
    assert reciprocal_rank_fusion([[(a, 1)], []]) == [(a, 1/61)]
    for invalid in (True, 0, -1, 1.5):
        with pytest.raises(ValueError):
            reciprocal_rank_fusion([], k=invalid)

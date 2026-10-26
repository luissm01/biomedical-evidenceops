"""Small-corpus BM25 and rank fusion. No models, persistence or services."""

from collections import Counter
import math
import re

from evidenceops.chunking import RetrievableUnit

BM25_K1 = 1.2
BM25_B = 0.75
RRF_K = 60
CANDIDATE_K = 50
TOKENIZER = "unicode-alphanumeric-casefold-v1"


def tokenize(text: str) -> list[str]:
    """Casefold, then Unicode alphanumeric runs; underscore is a separator.

    No stemming, stopwords, accent normalization, synonyms or medical rules.
    Hyphens and punctuation split terms; numbers are retained.
    """
    return re.findall(r"[^\W_]+", text.casefold())


def bm25(units: list[RetrievableUnit], query: str) -> list[tuple[RetrievableUnit, float]]:
    """BM25 with positive log1p IDF, k1=1.2, b=.75; only positive matches.

    Statistics use all eligible units (including empty token streams). Query
    terms count once. Rebuilt per call; memory grows with eligible corpus text.
    """
    terms = sorted(set(tokenize(query)))
    if not units or not terms:
        return []
    counts = [Counter(tokenize(unit.text)) for unit in units]
    lengths = [sum(count.values()) for count in counts]
    average = sum(lengths) / len(units)
    if not average:
        return []
    frequency = Counter(term for count in counts for term in count)
    results = []
    for unit, count, length in zip(units, counts, lengths, strict=True):
        score = 0.0
        for term in terms:
            tf = count[term]
            if tf:
                idf = math.log1p((len(units) - frequency[term] + .5) / (frequency[term] + .5))
                score += idf * tf * (BM25_K1 + 1) / (
                    tf + BM25_K1 * (1 - BM25_B + BM25_B * length / average)
                )
        if score > 0:
            results.append((unit, score))
    return sorted(results, key=lambda item: (-item[1], item[0].unit_id))


def reciprocal_rank_fusion(
    rankings: list[list[tuple[RetrievableUnit, float]]], *, k: int = RRF_K,
) -> list[tuple[RetrievableUnit, float]]:
    """Sum 1/(k + one-based rank); each unit contributes once per ranking."""
    if type(k) is not int or k <= 0:
        raise ValueError("RRF k must be a positive integer")
    units = {}
    contributions = {}
    for ranking in rankings:
        seen = set()
        for unit, _ in ranking:
            if unit.unit_id in seen:
                continue
            seen.add(unit.unit_id)
            rank = len(seen)
            units[unit.unit_id] = unit
            contributions.setdefault(unit.unit_id, []).append(1 / (k + rank))
    scores = {key: math.fsum(values) for key, values in contributions.items()}
    return [(units[key], scores[key]) for key in sorted(scores, key=lambda key: (-scores[key], key))]

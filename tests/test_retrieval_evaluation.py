"""Known rankings and isolated end-to-end evaluation, never model downloads."""

from collections import Counter
import json
import shutil

import pytest
from sqlalchemy import select, text

from evidenceops.embeddings import MedCPTConfig
from evidenceops.models import Publication
from evidenceops.retrieval_evaluation import (
    DEFAULT_DIRECTORY, aggregate_metrics, load_inputs,
    publication_metrics, run_baseline,
)


def test_known_rankings_and_full_mrr():
    assert publication_metrics(['x', 'a', 'y', 'b', 'z', 'c'], {'a', 'b', 'c'}) == {
        'hit_rate@5': 1.0, 'recall@5': 2/3, 'precision@5': 2/5, 'reciprocal_rank': 1/2,
    }
    assert publication_metrics(['x', 'y', 'z', 'u', 'v', 'a'], {'a'}) == {
        'hit_rate@5': 0.0, 'recall@5': 0.0, 'precision@5': 0.0, 'reciprocal_rank': 1/6,
    }
    assert publication_metrics(['x', 'a'], {'a'})['precision@5'] == 1/5
    assert publication_metrics([], {'a'})['reciprocal_rank'] == 0
    assert publication_metrics(['x'], set()) == {
        'hit_rate@5': 0.0, 'recall@5': None, 'precision@5': 0.0, 'reciprocal_rank': 0.0,
    }


def test_macro_average_and_queries_without_relevants():
    results = [{'metrics': publication_metrics(r, s)} for r, s in [
        (['a', 'b'], {'a', 'b'}), (['x', 'a'], {'a', 'z'}), (['x'], set()),
    ]]
    assert aggregate_metrics(results) == {
        'hit_rate@5': 2/3, 'recall@5': .75, 'precision@5': pytest.approx(.2),
        'mrr': .5, 'queries': 3, 'queries_with_relevants': 2,
    }
    assert aggregate_metrics([{'metrics': publication_metrics([], set())}])['recall@5'] is None
    with pytest.raises(ValueError):
        aggregate_metrics([])


@pytest.mark.parametrize('k', [0, -1, True, 2.5])
def test_invalid_k(k):
    with pytest.raises(ValueError):
        publication_metrics([], set(), k=k)


def test_duplicate_publications_are_not_double_counted():
    with pytest.raises(ValueError, match='duplicate'):
        publication_metrics(['a', 'a'], {'a'})


def test_frozen_dataset_contract():
    corpus, dataset, queries = load_inputs(DEFAULT_DIRECTORY)
    freeze = json.loads((DEFAULT_DIRECTORY / 'freeze-v1.json').read_text())
    assert freeze['pmids'] == [doc['source_id'] for doc in corpus['documents']]
    assert len(corpus['documents']) == 50
    assert set(Counter(d['area'] for d in corpus['documents']).values()) == {10}
    assert len(queries) == 10
    assert all(q.relevant for q in queries)
    assert sum(len(q.relevant) >= 2 for q in queries) >= 5
    assert dataset['judgments']['author'] == 'Codex-assisted; developer review pending'


def test_input_mutation_fails_before_encoder_or_database(tmp_path):
    for path in DEFAULT_DIRECTORY.glob('*-v1.json'):
        shutil.copy(path, tmp_path / path.name)
    path = tmp_path / 'queries-v1.json'
    path.write_text(path.read_text() + ' ')
    with pytest.raises(ValueError, match='Frozen input changed'):
        run_baseline(tmp_path, tmp_path / 'result.json', 'invalid', None)
    assert not (tmp_path / 'result.json').exists()


class FakeEncoder:
    config = MedCPTConfig()
    def __init__(self):
        self.article_calls = 0
        self.query_calls = 0
    def encode_article(self, unit):
        self.article_calls += 1
        # Stable distinct ordering, independently of judgments.
        return [float(int(unit.source_id) % 100000)] + [0.] * 767
    def encode_query(self, query):
        self.query_calls += 1
        return [1.] + [0.] * 767


@pytest.mark.parametrize("mode", ["semantic", "hybrid"])
def test_runner_isolated_schema_rankings_and_no_overwrite(mode, tmp_path, test_settings, migrated_database):
    from evidenceops.database import create_database
    engine, sessions = create_database(test_settings)
    with sessions() as session:
        before = session.scalars(select(Publication.id)).all()
    encoder = FakeEncoder()
    output = tmp_path / 'run.json'
    try:
        run = run_baseline(DEFAULT_DIRECTORY, output, str(test_settings.database_url), encoder, mode=mode)
        assert run['configuration']['mode'] == mode
        if mode == 'hybrid':
            assert run['configuration']['hybrid']['rrf_k'] == 60
            assert run['configuration']['hybrid']['candidate_k'] == 50
        assert run['status'] == 'complete'
        assert encoder.article_calls == 50 and encoder.query_calls == 10
        assert len(run['results']) == 10
        assert all(len(row['ranking']) == 50 and len(row['top_5']) == 5 for row in run['results'])
        assert json.loads(output.read_text()) == run
        with sessions() as session:
            assert session.scalars(select(Publication.id)).all() == before
            assert session.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'retrieval_eval_%'")) == 0
        with pytest.raises(FileExistsError):
            run_baseline(DEFAULT_DIRECTORY, output, str(test_settings.database_url), encoder)
        assert encoder.article_calls == 50
    finally:
        engine.dispose()


def test_runner_failed_inference_preserves_failure_and_cleans_schema(tmp_path, test_settings, migrated_database):
    encoder = FakeEncoder()
    def fail(unit):
        raise RuntimeError('sensitive details must not be saved')
    encoder.encode_article = fail
    output = tmp_path / 'failed.json'
    with pytest.raises(RuntimeError):
        run_baseline(DEFAULT_DIRECTORY, output, str(test_settings.database_url), encoder)
    run = json.loads(output.read_text())
    assert run['status'] == 'failed' and run['error_type'] == 'RuntimeError'
    assert 'sensitive' not in output.read_text() and 'aggregate' not in run
    from evidenceops.database import create_database
    engine, sessions = create_database(test_settings)
    try:
        with sessions() as session:
            assert session.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'retrieval_eval_%'")) == 0
    finally:
        engine.dispose()


def test_saved_real_baseline_integrity_and_recalculation():
    """Read-only artifact audit: never invoke a retriever or model."""
    from datetime import datetime
    from evidenceops.retrieval_evaluation import sha256
    corpus, dataset, queries = load_inputs(DEFAULT_DIRECTORY)
    run = json.loads((DEFAULT_DIRECTORY / 'baseline-v1.json').read_text())
    freeze = json.loads((DEFAULT_DIRECTORY / 'freeze-v1.json').read_text())
    assert run['status'] == 'complete'
    assert datetime.fromisoformat(freeze['frozen_at_utc']) < datetime.fromisoformat(run['started_at_utc'])
    assert run['input_sha256'] == {name: sha256(DEFAULT_DIRECTORY / name) for name in ('corpus-v1.json', 'queries-v1.json', 'freeze-v1.json')}
    assert run['configuration']['top_k'] == 5 and run['configuration']['published_from'] is None
    assert run['configuration']['dimensions'] == 768
    assert run['configuration']['similarity'] == 'inner-product'
    assert run['configuration']['strategy'] == 'whole-publication-v1'
    assert run['corpus_version'] == corpus['version'] and run['dataset_version'] == dataset['version']
    expected_pmids = {doc['source_id'] for doc in corpus['documents']}
    assert [row['query_id'] for row in run['results']] == [query.id for query in queries]
    for query, row in zip(queries, run['results'], strict=True):
        ranking = row['ranking']
        assert [item['rank'] for item in ranking] == list(range(1, 51))
        pmids = [item['pmid'] for item in ranking]
        assert set(pmids) == expected_pmids and len(pmids) == len(set(pmids))
        assert row['top_5'] == pmids[:5]
        assert row['query'] == query.query
        scores = [item['score'] for item in ranking]
        assert scores == sorted(scores, reverse=True)
        positives = {item.pmid for item in query.relevant}
        assert all(item['relevant'] == (item['pmid'] in positives) for item in ranking)
        assert row['metrics'] == publication_metrics(pmids, positives)
    assert run['aggregate'] == aggregate_metrics(run['results'])


@pytest.mark.parametrize('defect', ['duplicate_query', 'unknown_positive', 'duplicate_judgment', 'wrong_corpus'])
def test_semantically_invalid_dataset_even_with_updated_hash(tmp_path, defect):
    import hashlib
    for path in DEFAULT_DIRECTORY.glob('*-v1.json'):
        shutil.copy(path, tmp_path / path.name)
    path = tmp_path / 'queries-v1.json'
    dataset = json.loads(path.read_text())
    if defect == 'duplicate_query':
        dataset['queries'][1]['id'] = dataset['queries'][0]['id']
    elif defect == 'unknown_positive':
        dataset['queries'][0]['relevant'][0]['pmid'] = '999999999999'
    elif defect == 'duplicate_judgment':
        dataset['queries'][0]['ambiguous'].append(dataset['queries'][0]['relevant'][0])
    else:
        dataset['corpus_version'] = 'different'
    path.write_text(json.dumps(dataset))
    freeze_path = tmp_path / 'freeze-v1.json'
    freeze = json.loads(freeze_path.read_text())
    freeze['sha256']['queries-v1.json'] = hashlib.sha256(path.read_bytes()).hexdigest()
    freeze_path.write_text(json.dumps(freeze))
    with pytest.raises(ValueError):
        load_inputs(tmp_path)


def test_compare_preserved_baseline_and_reject_incompatible_runs():
    from copy import deepcopy
    from evidenceops.retrieval_comparison import compare
    baseline = json.loads((DEFAULT_DIRECTORY / 'baseline-v1.json').read_text())
    result = compare(baseline, baseline)
    assert all(value == 0 for value in result['aggregate_delta'].values())
    assert len(result['queries']) == 10
    assert all(not row['entered_top_5'] and not row['left_top_5'] for row in result['queries'])
    for key, value in [('status', 'failed'), ('input_sha256', {}), ('results', [])]:
        changed = deepcopy(baseline)
        changed[key] = value
        with pytest.raises(ValueError):
            compare(baseline, changed)
    changed = deepcopy(baseline)
    changed['results'][0]['metrics']['precision@5'] = -1
    with pytest.raises(ValueError):
        compare(baseline, changed)

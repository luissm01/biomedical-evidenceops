"""Cross-Encoder adapter and stage contracts, with no real ML libraries."""

from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
import sys
from uuid import UUID

import pytest

from evidenceops import retrieval
from evidenceops.chunking import build_retrievable_unit
from evidenceops.reranking import LocalMedCPTReranker, RerankerConfig, validate_scores
from test_retrieval import document


class FakeReranker:
    config = RerankerConfig()

    def __init__(self):
        self.calls = []

    def score(self, query, units):
        self.calls.append((query, units))
        return [float(i) - 30 for i in range(len(units))]


def results(count=25):
    return [retrieval.RetrievalResult(build_retrievable_unit(document(str(i)), publication_id=UUID(int=i+1)), float(count - i))
            for i in range(count)]


@pytest.fixture
def libraries(monkeypatch):
    logits = Mock()
    logits.squeeze.return_value.tolist.return_value = [-8., 6.]
    model = Mock(return_value=SimpleNamespace(logits=logits))
    model.to.return_value = model
    model.eval.return_value = model
    model.config.num_labels = 1
    tokenizer = Mock(return_value={'input_ids': object()})
    model_loader, tokenizer_loader = Mock(return_value=model), Mock(return_value=tokenizer)
    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(
        AutoModelForSequenceClassification=SimpleNamespace(from_pretrained=model_loader),
        AutoTokenizer=SimpleNamespace(from_pretrained=tokenizer_loader)))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(inference_mode=nullcontext, float32='float32'))
    return model, tokenizer, model_loader, tokenizer_loader


def test_lazy_pinned_cpu_raw_logits_pair_limit_and_reuse(libraries):
    model, tokenizer, model_loader, tokenizer_loader = libraries
    reranker = LocalMedCPTReranker()
    assert reranker.score('q', []) == []
    model_loader.assert_not_called()
    units = [r.unit for r in results(2)]
    units[1] = replace(units[1], text='Long title\n\n' + 'biomedical ' * 700)
    assert reranker.score(' q ', units) == [-8., 6.]
    tokenizer.assert_called_once_with([['q', unit.text] for unit in units],
        truncation='longest_first', max_length=512, padding=True, return_tensors='pt')
    for loader in (model_loader, tokenizer_loader):
        loader.assert_called_once_with(reranker.config.model, revision=reranker.config.revision)
    model.to.assert_called_once_with(device='cpu', dtype='float32')
    model.eval.assert_called_once()
    model.return_value.logits.squeeze.assert_called_once_with(dim=1)
    reranker.score('q', units)
    assert model_loader.call_count == 1
    with pytest.raises(ValueError, match='Query'):
        reranker.score(' ', units)


def test_bad_model_head_is_rejected(libraries):
    libraries[0].config.num_labels = 2
    with pytest.raises(ValueError, match='one logit'):
        LocalMedCPTReranker().score('q', [r.unit for r in results(1)])


@pytest.mark.parametrize('scores', [[1.], [1., float('nan')], [float('inf'), 2.]])
def test_bad_scores_are_rejected(scores):
    with pytest.raises(ValueError, match='finite'):
        validate_scores(scores, 2)


def test_fixed_candidates_filters_trace_and_timing(monkeypatch):
    first = Mock(return_value=results(20))
    monkeypatch.setattr(retrieval, '_search_first_stage', first)
    clock = iter([1., 3., 8.])
    monkeypatch.setattr(retrieval, 'perf_counter', lambda: next(clock))
    reranker, latency = FakeReranker(), {}
    found = retrieval.search(None, None, query=' q ', top_k=5, mode='reranking',
                             published_from=2024, reranker=reranker, timings=latency)
    assert first.call_args.kwargs['top_k'] == 20
    assert first.call_args.kwargs['mode'] == 'semantic'
    assert first.call_args.kwargs['published_from'] == 2024
    assert [r.unit for r in found] == [r.unit for r in reversed(first.return_value[-5:])]
    assert [r.retrieval_score for r in found] == [r.score for r in reversed(first.return_value[-5:])]
    assert reranker.calls == [('q', [r.unit for r in first.return_value])]
    assert latency == {'retrieval_seconds': 2., 'reranker_seconds': 5., 'total_seconds': 7.}


def test_empty_ties_failures_and_semantic_does_not_call_reranker(monkeypatch):
    first = Mock(return_value=[])
    monkeypatch.setattr(retrieval, '_search_first_stage', first)
    reranker = Mock(config=RerankerConfig())
    assert retrieval.search(None, None, query='q', top_k=5, mode='reranking', reranker=reranker) == []
    reranker.score.assert_not_called()
    first.return_value = results(3)
    reranker.score.return_value = [-2.] * 3
    found = retrieval.search(None, None, query='q', top_k=5, mode='reranking', reranker=reranker)
    assert [r.unit.unit_id for r in found] == sorted(r.unit.unit_id for r in first.return_value)
    reranker.score.reset_mock()
    assert retrieval.search(None, None, query='q', top_k=5, reranker=reranker) == first.return_value
    reranker.score.assert_not_called()
    reranker.score.side_effect = RuntimeError('unavailable')
    with pytest.raises(RuntimeError):
        retrieval.search(None, None, query='q', top_k=5, mode='reranking', reranker=reranker)
    reranker.score.side_effect = None
    reranker.score.return_value = [1.]
    with pytest.raises(ValueError):
        retrieval.search(None, None, query='q', top_k=5, mode='reranking', reranker=reranker)


@pytest.mark.parametrize('options', [{'top_k': 21, 'reranker': FakeReranker()}, {'top_k': 5},
                                    {'top_k': True, 'reranker': FakeReranker()}])
def test_invalid_reranking_fails_before_retrieval(monkeypatch, options):
    first = Mock()
    monkeypatch.setattr(retrieval, '_search_first_stage', first)
    with pytest.raises(ValueError):
        retrieval.search(None, None, query='q', mode='reranking', **options)
    first.assert_not_called()


def test_reranking_json_log_records_model_revision_without_content(monkeypatch):
    import io
    import json
    import logging
    from evidenceops.observability import JsonFormatter
    monkeypatch.setattr(retrieval, '_search_first_stage', Mock(return_value=results(2)))
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger('evidenceops.retrieval')
    level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        reranker = FakeReranker()
        retrieval.search(None, None, query='private-query', top_k=5, mode='reranking', reranker=reranker)
        event = json.loads(stream.getvalue())
        assert event['reranker_model'] == reranker.config.model
        assert event['reranker_revision'] == reranker.config.revision
        assert event['candidate_count'] == 2
        assert 'private-query' not in stream.getvalue()
        assert 'Treatment evidence' not in stream.getvalue()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)

"""RAG evaluation artifacts and human review; no network, model inference or DB."""

from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4

import pytest

from evidenceops import evaluation_review as human
from evidenceops import rag_evaluation as evaluation
from evidenceops.biomedical import BiomedicalDocument
from evidenceops.chunking import build_retrievable_unit
from evidenceops.config import GenerationSettings
from evidenceops.embeddings import MedCPTConfig
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause
from evidenceops.rag import ABSTENTION_ANSWER, RAG_SYSTEM_INSTRUCTION
from evidenceops.retrieval import RetrievalResult


class Generator:
    def __init__(self, content=None):
        self.calls = []
        self.content = content or GeneratedContent(answer='Síntesis de prueba [S1].', limitations=[])

    def generate(self, message, *, system_instruction=None):
        self.calls.append((message, system_instruction))
        return self.content


def corpus_results():
    _, corpus = evaluation.inputs(evaluation.DEFAULT_DATASET)
    return [RetrievalResult(build_retrievable_unit(BiomedicalDocument(**{
        k: v for k, v in d.items() if k != 'area'}), publication_id=uuid4()), 1.0)
        for d in corpus['documents']]


@pytest.fixture
def artifact(tmp_path):
    retrieved = corpus_results()[:5]
    generator = Generator()
    settings = GenerationSettings(_env_file=None, gemini_api_key='never-serialize-this')
    path = evaluation.run_evaluation(generator, lambda **kw: retrieved,
        dataset_path=evaluation.DEFAULT_DATASET, settings=settings,
        encoder_configuration=MedCPTConfig().metadata(), output_dir=tmp_path)
    return path, evaluation.RagRun.model_validate_json(path.read_bytes()), generator


def complete_review(run):
    review = human.prepare_review(run, evaluation.DEFAULT_DATASET)
    review.reviewer = 'Artificial test judgments; not a real review'
    for item in review.results:
        item.verdict = 'pass'
    return review


def test_dataset_documentary_freeze_and_distribution():
    dataset, corpus = evaluation.inputs(evaluation.DEFAULT_DATASET)
    assert len(corpus['documents']) == 50 and len(dataset.cases) == 10
    assert len({d for c in dataset.cases for d in c.dimensions}) == 6
    assert dataset.annotation['review_status'] == 'approved-by-developer-with-r09-correction'
    assert all(c.scenario_reason and c.reference_facts and c.expected_behavior for c in dataset.cases)


def test_frozen_mutation_prevents_calls(tmp_path):
    for name in ('cases-v1.json', 'freeze-v1.json'):
        (tmp_path / name).write_bytes((evaluation.DEFAULT_DATASET.parent / name).read_bytes())
    path = tmp_path / 'cases-v1.json'
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError, match='inputs changed'):
        evaluation.run_evaluation(None, None, dataset_path=path,
            settings=GenerationSettings(_env_file=None), encoder_configuration={}, output_dir=tmp_path)
    assert len(list(tmp_path.glob('*.json'))) == 2


def test_actual_service_trace_roundtrip_and_no_rubric_leak(artifact):
    path, run, generator = artifact
    evaluation.validate_run(run, evaluation.DEFAULT_DATASET)
    assert run.status == 'complete' and len(generator.calls) == 10
    assert run.provider == 'gemini' and run.finished_at_utc
    assert run.source_sha256['uv.lock']
    assert 'never-serialize-this' not in path.read_text()
    for message, instruction in generator.calls:
        data = json.loads(message)
        assert set(data) == {'query', 'evidence'}
        assert instruction == RAG_SYSTEM_INSTRUCTION
    assert human.prepare_review(run, evaluation.DEFAULT_DATASET).review_version == 'rag-1'
    assert len(human.prepare_review(run, evaluation.DEFAULT_DATASET).results) == 60
    assert all(j.verdict is None for j in human.prepare_review(run, evaluation.DEFAULT_DATASET).results)


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'status', 'question', 'corpus',
                                     'source_text', 'source_identity', 'source_order', 'output', 'diagnostic', 'generated'])
def test_baseline_rejects_incomplete_or_tampered_traces(artifact, mutation):
    _, original, _ = artifact
    run = original.model_copy(deep=True)
    if mutation == 'missing':
        run.cases.pop()
    elif mutation == 'duplicate':
        run.cases[1] = run.cases[0]
    elif mutation == 'status':
        run.status = 'running'
    elif mutation == 'question':
        run.cases[0].question = 'Different input'
    elif mutation == 'corpus':
        run.corpus_sha256 = '0' * 64
    elif mutation == 'source_text':
        r = run.cases[0].retrieved[0]
        run.cases[0].retrieved[0] = replace(r, unit=replace(r.unit, text='mutated'))
    elif mutation == 'source_identity':
        r = run.cases[0].retrieved[0]
        run.cases[0].retrieved[0] = replace(r, unit=replace(r.unit, unit_id='fabricated'))
    elif mutation == 'source_order':
        run.cases[0].retrieved.reverse()
    elif mutation == 'output':
        run.cases[0].output.answer = 'different [S1]'
    elif mutation == 'diagnostic':
        run.cases[0].diagnostics['expected_not_retrieved'] = ['fabricated']
    else:
        run.cases[0].generated = None
    with pytest.raises(ValueError):
        evaluation.validate_run(run, evaluation.DEFAULT_DATASET)


def test_citation_failure_retains_generated_output_and_safe_diagnostic():
    case = evaluation.inputs(evaluation.DEFAULT_DATASET)[0].cases[0]
    generator = Generator(GeneratedContent(answer='Respuesta sin cita.', limitations=[]))
    result = evaluation.evaluate_case(case, lambda **kw: corpus_results()[:5], generator)
    assert result.status == 'error' and result.error_stage == 'citations'
    assert result.error == GenerationErrorCause.INVALID_OUTPUT
    assert result.generated.answer == 'Respuesta sin cita.' and result.output is None
    assert result.diagnostic['validation_reason'] == 'block_missing_citation'
    assert result.context and len(generator.calls) == 1


def test_transport_error_and_retrieval_error_are_not_content_failures():
    case = evaluation.inputs(evaluation.DEFAULT_DATASET)[0].cases[0]

    class Timeout:
        def generate(self, *args, **kwargs):
            raise GenerationError(GenerationErrorCause.TIMEOUT, 'do not serialize secrets')

    result = evaluation.evaluate_case(case, lambda **kw: corpus_results()[:5], Timeout())
    assert result.error_stage == 'generation' and result.error == GenerationErrorCause.TIMEOUT

    def unavailable(**kw):
        raise RuntimeError('do not serialize secrets')

    result = evaluation.evaluate_case(case, unavailable, Generator())
    assert result.error_stage == 'retrieval' and not result.context
    assert 'do not serialize secrets' not in result.model_dump_json()


def test_no_results_and_budget_loss_skip_provider_and_remain_distinct():
    case = evaluation.inputs(evaluation.DEFAULT_DATASET)[0].cases[0]
    generator = Generator()
    absent = evaluation.evaluate_case(case, lambda **kw: [], generator)
    first = corpus_results()[0]
    oversized = replace(first, unit=replace(first.unit, text='x' * 21000))
    lost = evaluation.evaluate_case(case, lambda **kw: [oversized], generator)
    assert not generator.calls
    assert absent.output.answer == lost.output.answer == ABSTENTION_ANSWER
    assert absent.diagnostics['expected_lost_from_context'] == []
    assert lost.diagnostics['expected_lost_from_context'] == [first.unit.source_id]
    assert absent.diagnostics['expected_not_retrieved']
    assert lost.context.omitted


def test_failed_run_continues_and_cannot_prepare_or_promote(tmp_path):
    count = 0

    def retrieve(**kw):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError('sensitive failure details')
        return []

    path = evaluation.run_evaluation(Generator(), retrieve, dataset_path=evaluation.DEFAULT_DATASET,
        settings=GenerationSettings(_env_file=None), encoder_configuration={}, output_dir=tmp_path)
    run = evaluation.RagRun.model_validate_json(path.read_bytes())
    assert count == 10 and run.status == 'failed'
    assert len(run.cases) == 10 and run.cases[1].error_stage == 'retrieval'
    assert 'sensitive failure details' not in path.read_text()
    with pytest.raises(SystemExit) as exc:
        evaluation.main(['prepare', str(path), str(tmp_path / 'review.json')])
    assert exc.value.code == 2
    assert not (tmp_path / 'review.json').exists()


def test_setup_error_saved_before_any_generation(tmp_path):
    @contextmanager
    def fail_setup():
        raise RuntimeError('private DB connection details')
        yield

    generator = Generator()
    path = evaluation.run_evaluation(generator, None, dataset_path=evaluation.DEFAULT_DATASET,
        settings=GenerationSettings(_env_file=None), encoder_configuration={}, output_dir=tmp_path,
        retrieval_context=fail_setup)
    run = evaluation.RagRun.model_validate_json(path.read_bytes())
    assert run.status == 'failed' and not run.cases and not generator.calls
    assert run.operation_error == {'stage': 'infrastructure', 'type': 'RuntimeError'}
    assert 'private DB' not in path.read_text()


def test_interrupt_preserves_checkpoint_and_is_never_baseline(tmp_path):
    calls = 0

    def retrieve(**kw):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise KeyboardInterrupt()
        return []

    with pytest.raises(KeyboardInterrupt):
        evaluation.run_evaluation(Generator(), retrieve, dataset_path=evaluation.DEFAULT_DATASET,
            settings=GenerationSettings(_env_file=None), encoder_configuration={}, output_dir=tmp_path)
    run = evaluation.RagRun.model_validate_json(next(tmp_path.glob('*.json')).read_bytes())
    assert run.status == 'running' and len(run.cases) == 2
    with pytest.raises(ValueError):
        evaluation.validate_run(run, evaluation.DEFAULT_DATASET)


def test_review_complete_binding_regression_and_applicability(artifact):
    _, run, _ = artifact
    baseline = complete_review(run)
    candidate = baseline.model_copy(deep=True)
    baseline.results[0].verdict = 'fail'
    baseline.results[0].notes = 'Artificial unsupported assertion'
    candidate.results[1].verdict = 'fail'
    candidate.results[1].notes = 'Artificial semantic citation mismatch'
    report = human.compare(baseline, run, candidate, run, evaluation.DEFAULT_DATASET)
    assert len(report['improvements']) == len(report['regressions']) == 1
    assert human.aggregate(candidate, run, evaluation.DEFAULT_DATASET)['counts']['fail'] == 1
    candidate.run_sha256 = '0' * 64
    with pytest.raises(ValueError):
        human.aggregate(candidate, run, evaluation.DEFAULT_DATASET)
    baseline.results[1].verdict = 'not_applicable'
    baseline.results[1].notes = 'An excuse cannot hide a citation error on a substantive answer'
    with pytest.raises(ValueError, match='N/A only'):
        human.validate_review(baseline, run, evaluation.DEFAULT_DATASET)


def test_justified_na_and_cli_no_overwrite(tmp_path, capsys):
    path = evaluation.run_evaluation(Generator(), lambda **kw: [], dataset_path=evaluation.DEFAULT_DATASET,
        settings=GenerationSettings(_env_file=None), encoder_configuration={}, output_dir=tmp_path)
    run = evaluation.RagRun.model_validate_json(path.read_bytes())
    review = complete_review(run)
    for item in review.results:
        if item.dimension == 'citation_semantics':
            item.verdict = 'not_applicable'
            item.notes = 'Exact abstention: no substantive citations to assess'
    report = human.aggregate(review, run, evaluation.DEFAULT_DATASET)
    assert report['counts'] == {'pass': 50, 'fail': 0, 'not_applicable': 10}
    review_path = tmp_path / 'review.json'
    assert evaluation.main(['prepare', str(path), str(review_path)]) == 0
    with pytest.raises(SystemExit):
        evaluation.main(['promote', str(path), str(review_path), str(tmp_path / 'baseline.json')])
    review_path.write_text(review.model_dump_json())
    assert evaluation.main(['aggregate', str(path), str(review_path)]) == 0
    assert evaluation.main(['compare', str(path), str(review_path), str(path), str(review_path)]) == 0
    baseline = tmp_path / 'baseline.json'
    assert evaluation.main(['promote', str(path), str(review_path), str(baseline)]) == 0
    assert baseline.read_bytes() == path.read_bytes()
    assert baseline.with_suffix('.review.json').read_bytes() == review_path.read_bytes()
    with pytest.raises(SystemExit):
        evaluation.main(['promote', str(path), str(review_path), str(baseline)])
    with pytest.raises(SystemExit):
        evaluation.main(['prepare', str(path), str(review_path)])
    with pytest.raises(SystemExit) as exc:
        evaluation.main(['run'])
    assert exc.value.code == 2


def test_fail_and_na_always_require_reason():
    for verdict in ('fail', 'not_applicable'):
        with pytest.raises(ValueError):
            human.Judgment(case_id='r01', dimension='citation_semantics', verdict=verdict)


def test_applicability_changes_do_not_count_as_improvements(artifact, tmp_path):
    _, baseline_run, _ = artifact
    path = evaluation.run_evaluation(Generator(), lambda **kw: [], dataset_path=evaluation.DEFAULT_DATASET,
        settings=GenerationSettings(_env_file=None), encoder_configuration={}, output_dir=tmp_path)
    candidate_run = evaluation.RagRun.model_validate_json(path.read_bytes())
    baseline, candidate = complete_review(baseline_run), complete_review(candidate_run)
    for item in candidate.results:
        if item.dimension == 'citation_semantics':
            item.verdict = 'not_applicable'
            item.notes = 'No substantive claims in exact abstention'
    report = human.compare(baseline, baseline_run, candidate, candidate_run, evaluation.DEFAULT_DATASET)
    assert len(report['applicability_changes']) == 10
    assert not report['regressions'] and not report['improvements']


def test_cli_live_wiring_with_only_fakes_and_cleanup(tmp_path, monkeypatch, capsys):
    """Exercise composition of resources; --live here never reaches real services."""
    import sys
    from types import SimpleNamespace
    from evidenceops import embeddings, generator_factory
    from evidenceops.config import Settings

    lifecycle = []
    settings = Settings(_env_file=None, database_url='postgresql+psycopg://fake@localhost/fake',
                        gemini_api_key='test-key-must-not-be-saved')

    class ClosingGenerator(Generator):
        def close(self):
            lifecycle.append('generator_closed')

    generator = ClosingGenerator()

    @contextmanager
    def fake_sessions(corpus, database_url, encoder, environment):
        assert len(corpus['documents']) == 50
        lifecycle.append('opened')
        environment.update(postgresql='test-version', pgvector_extension='test-vector')
        try:
            yield object()
        finally:
            lifecycle.append('schema_cleaned')

    monkeypatch.setattr(evaluation, 'Settings', lambda: settings)
    monkeypatch.setattr(evaluation, 'frozen_sessions', fake_sessions)
    monkeypatch.setattr(evaluation, 'search', lambda *args, **kwargs: [])
    monkeypatch.setattr(embeddings, 'LocalMedCPT', lambda: SimpleNamespace(config=MedCPTConfig()))
    monkeypatch.setattr(generator_factory, 'create_generator', lambda settings: generator)
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(get_num_threads=lambda: 2,
                                                            get_num_interop_threads=lambda: 1))
    assert evaluation.main(['run', '--live', '--output-dir', str(tmp_path)]) == 0
    path = Path(capsys.readouterr().out.strip())
    run = evaluation.RagRun.model_validate_json(path.read_bytes())
    evaluation.validate_run(run, evaluation.DEFAULT_DATASET)
    assert run.environment['postgresql'] == 'test-version'
    assert run.environment['torch_threads'] == 2
    assert lifecycle == ['opened', 'schema_cleaned', 'generator_closed']
    assert not generator.calls and 'test-key-must-not-be-saved' not in path.read_text()


def test_annotations_cannot_change_retrieval_or_provider_context():
    """Poison every evaluation-only field; provider inputs must remain identical."""
    dataset, _ = evaluation.inputs(evaluation.DEFAULT_DATASET)
    case = dataset.cases[0]
    changed = case.model_copy(deep=True)
    changed.reference_facts = ['REFERENCE_FACT_MUST_NOT_LEAK']
    changed.expected_behavior = ['EXPECTED_BEHAVIOR_MUST_NOT_LEAK']
    changed.forbidden_claims = ['FORBIDDEN_CLAIM_MUST_NOT_LEAK']
    changed.scenario_reason = 'SCENARIO_REASON_MUST_NOT_LEAK'
    changed.expected_pmids = [corpus_results()[-1].unit.source_id]
    changed.related_pmids = []
    changed.references = []
    changed.scenario = 'absent'
    retrieved = corpus_results()[:5]
    calls = []

    def retrieve(**kwargs):
        calls.append(kwargs)
        return retrieved

    original_generator, changed_generator = Generator(), Generator()
    before = evaluation.evaluate_case(case, retrieve, original_generator)
    after = evaluation.evaluate_case(changed, retrieve, changed_generator)
    assert calls == [{'query': case.question, 'top_k': 5, 'published_from': None}] * 2
    assert original_generator.calls == changed_generator.calls
    assert before.context == after.context
    assert before.output == after.output
    assert before.diagnostics != after.diagnostics  # Labels affect only post-run diagnostics.
    assert 'MUST_NOT_LEAK' not in json.dumps(changed_generator.calls)


def test_grounded_negative_answer_and_justified_abstention_can_pass(tmp_path):
    """Artificial human judgments: validate admissibility, never semantic quality."""
    dataset, _ = evaluation.inputs(evaluation.DEFAULT_DATASET)
    lookup = {r.unit.source_id: r for r in corpus_results()}
    case_by_query = {c.question: c for c in dataset.cases}

    def retrieve(**kwargs):
        case = case_by_query[kwargs['query']]
        ids = case.expected_pmids or case.related_pmids
        return [lookup[pmid] for pmid in ids][:5]

    class Responses:
        def generate(self, message, **kwargs):
            case = case_by_query[json.loads(message)['query']]
            if case.id in ('r07', 'r08'):
                return GeneratedContent(answer=ABSTENTION_ANSWER, limitations=[])
            if case.id == 'r10':
                return GeneratedContent(
                    answer='No: ENHANCE estudió EPOC; no demuestra eficacia en asma grave [S1].',
                    limitations=['Estos resultados no establecen eficacia ni ineficacia en asma [S1].'])
            return GeneratedContent(answer='Síntesis artificial [S1].', limitations=[])

    path = evaluation.run_evaluation(Responses(), retrieve, dataset_path=evaluation.DEFAULT_DATASET,
        settings=GenerationSettings(_env_file=None), encoder_configuration={}, output_dir=tmp_path)
    run = evaluation.RagRun.model_validate_json(path.read_bytes())
    review = complete_review(run)
    for item in review.results:
        if item.case_id in ('r07', 'r08') and item.dimension == 'citation_semantics':
            item.verdict = 'not_applicable'
            item.notes = 'Exact abstention without substantive citations'
    report = human.aggregate(review, run, evaluation.DEFAULT_DATASET)
    assert {'r07', 'r08', 'r10'} <= set(report['fully_passed_cases'])
    assert report['counts'] == {'pass': 58, 'fail': 0, 'not_applicable': 2}

"""Audit the promoted, human-reviewed baseline without models, network or DB."""

import hashlib
import json
from pathlib import Path
import tarfile

from evidenceops import evaluation_review as human
from evidenceops import rag_evaluation as evaluation

DIRECTORY = evaluation.DEFAULT_DATASET.parent


def artifacts():
    run = evaluation.RagRun.model_validate_json((DIRECTORY / 'baseline-v1.json').read_bytes())
    review = human.Review.model_validate_json((DIRECTORY / 'baseline-v1.review.json').read_bytes())
    return run, review


def test_promoted_baseline_and_source_snapshot_integrity():
    run, review = artifacts()
    evaluation.validate_run(run, evaluation.DEFAULT_DATASET)
    human.validate_review(review, run, evaluation.DEFAULT_DATASET)
    provenance = json.loads((DIRECTORY / 'baseline-v1.provenance.json').read_bytes())
    for field, file in [('raw_run', 'baseline-v1.json'), ('review', 'baseline-v1.review.json'),
                        ('aggregate', 'baseline-v1.aggregate.json'), ('snapshot', 'baseline-v1.inputs-and-code.tar.gz')]:
        assert hashlib.sha256((DIRECTORY / file).read_bytes()).hexdigest() == provenance[field + '_sha256']
    assert human.run_digest(run) == provenance['canonical_run_sha256']
    with tarfile.open(DIRECTORY / 'baseline-v1.inputs-and-code.tar.gz', 'r:gz') as archive:
        assert all('.env' not in Path(member.name).parts for member in archive.getmembers())
        for name, digest in run.source_sha256.items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest
        for name, digest in [('evaluation/rag/cases-v1.json', run.dataset_sha256),
                             ('evaluation/rag/freeze-v1.json', run.freeze_sha256),
                             ('evaluation/retrieval/corpus-v1.json', run.corpus_sha256)]:
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest


def test_reproduce_exact_aggregate_and_approved_sixty_pairs(capsys):
    assert evaluation.main(['aggregate', str(DIRECTORY / 'baseline-v1.json'),
                            str(DIRECTORY / 'baseline-v1.review.json')]) == 0
    actual = json.loads(capsys.readouterr().out)
    expected = json.loads((DIRECTORY / 'baseline-v1.aggregate.json').read_bytes())
    assert actual == expected
    assert actual['counts'] == {'pass': 58, 'fail': 0, 'not_applicable': 2}
    assert len(actual['results']) == 60 and actual['fully_passed_case_count'] == 10
    assert actual['failures'] == []
    for case_id in (f'r{i:02d}' for i in range(1, 11)):
        judgments = [j for j in actual['results'] if j['case_id'] == case_id]
        assert len(judgments) == 6 and len({j['dimension'] for j in judgments}) == 6
        na = [j for j in judgments if j['verdict'] == 'not_applicable']
        assert len(na) == (1 if case_id in ('r07', 'r08') else 0)
        assert all(j['dimension'] == 'citation_semantics' and j['notes'].strip() for j in na)


def test_abstention_normalization_and_no_positive_denominators():
    run, _ = artifacts()
    for case in run.cases:
        assert len(case.retrieved) == 5 and not case.context.omitted
        if case.case_id in ('r07', 'r08'):
            assert case.generated.answer == case.output.answer == evaluation.ABSTENTION_ANSWER
            assert case.generated.limitations == []
            assert case.output.limitations == ['Las fuentes proporcionadas no permiten responder a la pregunta.']
            assert len(case.context.sources) == 5
    summary = evaluation.diagnostic_summary(run)
    assert summary['technical_errors'] == [] and summary['cases_with_reference_context_loss'] == []
    # Absent/distractor questions without positives must not depress these means.
    assert summary['retrieval_reference_coverage']['queries'] == 7
    assert summary['retrieval_reference_coverage']['hit_rate@5'] == 1
    assert summary['retrieval_reference_coverage']['recall@5'] == 1
    assert all(c.diagnostics['retrieval_metrics']['recall@5'] is None
               for c in run.cases if c.case_id in ('r07', 'r08', 'r10'))
    observations = json.loads((DIRECTORY / 'baseline-v1.observations.json').read_bytes())
    assert observations['run_id'] == str(run.run_id)
    assert {o['case_id'] for o in observations['case_observations']} == {c.case_id for c in run.cases}

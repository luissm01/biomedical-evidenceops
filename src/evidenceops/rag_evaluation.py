"""Frozen-corpus, sequential RAG evaluation; live inference requires an explicit CLI flag."""

import argparse
from contextlib import ExitStack, closing
from datetime import UTC, datetime
from functools import partial
import json
from math import isfinite
from pathlib import Path
import platform
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from evidenceops import evaluation_review as human
from evidenceops.config import GenerationSettings, Settings
from evidenceops.evaluation import Dataset, Result, Run, Text, git_state, validate_baseline
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause
from evidenceops.rag import (
    ABSTENTION_ANSWER, EVIDENCE_CHARACTER_LIMIT, RAG_SYSTEM_INSTRUCTION,
    RagContext, RagService, build_context, validate_citations,
)
from evidenceops.rag_errors import InvalidCitationsError, RagRetrievalError
from evidenceops.retrieval import RetrievalResult, search
from evidenceops.retrieval_evaluation import (
    DEFAULT_DIRECTORY as RETRIEVAL_DIRECTORY, ROOT, _write, frozen_sessions,
    aggregate_metrics, load_inputs, package_version, publication_metrics, sha256,
)

DEFAULT_DATASET = ROOT / 'evaluation/rag/cases-v1.json'


class Reference(BaseModel):
    pmid: Text
    title: Text
    url: Text
    evidence_excerpt: Text


class RagCase(human.RubricCase):
    scenario: Literal['sufficient', 'partial', 'absent', 'distractors']
    published_from: int | None = Field(default=None, gt=0)
    expected_pmids: list[Text]
    related_pmids: list[Text]
    scenario_reason: Text
    references: list[Reference]


class RagDataset(Dataset):
    corpus_version: Text
    annotation: dict
    cases: list[RagCase]


class RagResult(Result):
    retrieved: list[RetrievalResult] = Field(default_factory=list)
    context: RagContext | None = None
    generated: GeneratedContent | None = None
    error_stage: Literal['retrieval', 'context', 'generation', 'citations'] | None = None
    diagnostic: dict = Field(default_factory=dict)
    diagnostics: dict = Field(default_factory=dict)


class RagRun(Run):
    run_version: Literal['rag-1'] = 'rag-1'
    pipeline_version: Literal['rag-v1-D026'] = 'rag-v1-D026'
    status: Literal['running', 'complete', 'failed'] = 'running'
    provider: Text
    corpus_version: Text
    corpus_sha256: Text
    freeze_sha256: Text
    configuration: dict
    source_sha256: dict[str, str]
    environment: dict
    cases: list[RagResult]
    finished_at_utc: datetime | None = None
    operation_error: dict = Field(default_factory=dict)

    def validate_artifacts(self, dataset_path: Path) -> None:
        validate_trace(self, dataset_path)

    def validate_human_judgments(self, review):
        for judgment in review.results:
            if judgment.verdict == 'not_applicable':
                case = next((c for c in self.cases if c.case_id == judgment.case_id), None)
                if (judgment.dimension != 'citation_semantics' or case is None
                        or case.output is None or case.output.answer != ABSTENTION_ANSWER):
                    raise ValueError('N/A only for citation semantics on exact abstention')


def inputs(dataset_path: Path, corpus_directory: Path = RETRIEVAL_DIRECTORY):
    # M7 remains the single source of truth for corpus loading/freeze validation.
    corpus, _, _ = load_inputs(corpus_directory)
    dataset = RagDataset.model_validate_json(dataset_path.read_bytes())
    frozen = json.loads((dataset_path.parent / 'freeze-v1.json').read_bytes())
    if (frozen['sha256']['cases-v1.json'] != sha256(dataset_path)
            or frozen['sha256']['corpus-v1.json'] != sha256(corpus_directory / 'corpus-v1.json')
            or dataset.corpus_version != corpus['version']):
        raise ValueError('RAG inputs changed; freeze a new dataset version before inference')
    documents = {d['source_id']: d for d in corpus['documents']}
    if len(dataset.cases) != 10 or {s: sum(c.scenario == s for c in dataset.cases) for s in
            ('sufficient', 'partial', 'absent', 'distractors')} != {
                'sufficient': 4, 'partial': 2, 'absent': 2, 'distractors': 2}:
        raise ValueError('Expected the agreed ten-case scenario distribution')
    for case in dataset.cases:
        if set(case.dimensions) != {'groundedness', 'citation_semantics', 'relevance',
                                    'unsupported_claims', 'abstention', 'limitations'}:
            raise ValueError('Every RAG case requires all six agreed dimensions')
        if ((case.scenario in ('sufficient', 'partial') and not case.expected_pmids)
                or (case.scenario == 'absent' and case.expected_pmids)):
            raise ValueError('Evidence anchors conflict with scenario')
        pmids = case.expected_pmids + case.related_pmids
        if len(pmids) != len(set(pmids)) or not set(pmids) <= documents.keys():
            raise ValueError('Unknown or duplicate reference PMID')
        if {r.pmid for r in case.references} != set(pmids):
            raise ValueError('Every annotated publication requires documentary evidence')
        for ref in case.references:
            doc = documents[ref.pmid]
            if (ref.title != doc['title'] or ref.url != doc['source_url']
                    or ref.evidence_excerpt not in doc['abstract']):
                raise ValueError('Reference differs from frozen evidence')
    return dataset, corpus


def evaluate_case(case: RagCase, retrieve, generator) -> RagResult:
    """Observe the actual service path once. No second retrieval or generation."""
    result = RagResult(case_id=case.id, question=case.question, status='error',
                       error=GenerationErrorCause.UNKNOWN, error_stage='retrieval')

    def retrieval(**kwargs):
        result.retrieved = retrieve(**kwargs)
        result.error_stage = 'context'
        return result.retrieved

    def context_observer(context):
        result.context = context
        result.error_stage = 'generation'

    class RecordingGenerator:
        def generate(self, question_text, *, system_instruction=None):
            result.generated = generator.generate(question_text, system_instruction=system_instruction)
            result.error_stage = 'citations'
            return result.generated

    service = RagService(retrieval, RecordingGenerator(), context_observer=context_observer)
    try:
        response = service.generate(case.question, published_from=case.published_from)
        result.output = GeneratedContent(answer=response.answer, limitations=response.limitations)
        result.status, result.error, result.error_stage = 'success', None, None
    except Exception as exc:
        if isinstance(exc, GenerationError):
            result.error = exc.cause
        if isinstance(exc, InvalidCitationsError):
            result.diagnostic = exc.diagnostic()
        elif isinstance(exc, RagRetrievalError):
            result.diagnostic = {'cause': exc.cause}
        # Never serialize arbitrary exception messages or provider bodies.
    expected = set(case.expected_pmids)
    ranked = [r.unit.source_id for r in result.retrieved]
    included = {s.unit.source_id for s in result.context.sources} if result.context else set()
    result.diagnostics = {
        'retrieval_metrics': publication_metrics(ranked, expected),
        'expected_not_retrieved': sorted(expected - set(ranked)),
        'expected_lost_from_context': sorted((expected & set(ranked)) - included),
        'expected_in_context': sorted(expected & included),
        'abstained': result.output.answer == ABSTENTION_ANSWER if result.output else None,
    }
    return result


def run_evaluation(generator, retrieve, *, dataset_path: Path, settings: GenerationSettings,
                   encoder_configuration: dict, output_dir: Path, repo: Path = ROOT,
                   corpus_directory: Path = RETRIEVAL_DIRECTORY, environment: dict | None = None,
                   retrieval_context=None) -> Path:
    dataset, corpus = inputs(dataset_path, corpus_directory)
    commit, dirty = git_state(repo)
    run = RagRun(
        run_id=uuid4(), timestamp_utc=datetime.now(UTC), dataset_version=dataset.dataset_version,
        dataset_sha256=sha256(dataset_path), git_commit=commit, working_tree_dirty=dirty,
        provider=settings.llm_provider, model=settings.selected_model,
        max_output_tokens=settings.selected_max_output_tokens,
        timeout_seconds=settings.selected_timeout_seconds, corpus_version=corpus['version'],
        corpus_sha256=sha256(corpus_directory / 'corpus-v1.json'),
        freeze_sha256=sha256(dataset_path.parent / 'freeze-v1.json'),
        configuration={'retrieval': encoder_configuration, 'top_k': 5,
                       'ranking': 'exact-pgvector', 'tie_break': 'unit_id ascending',
                       'evidence_character_limit': EVIDENCE_CHARACTER_LIMIT,
                       'system_instruction': RAG_SYSTEM_INSTRUCTION,
                       'published_from_by_case': {c.id: c.published_from for c in dataset.cases},
                       'retry_policy': 'existing-provider-adapter; no runner retries'},
        source_sha256={str(p.relative_to(ROOT)): sha256(p) for p in
                       [*(ROOT / 'src/evidenceops').glob('*.py'), ROOT / 'uv.lock']},
        environment={'python': platform.python_version(), 'platform': platform.platform(),
                     'packages': {name: package_version(name) for name in
                                  ('torch', 'transformers', 'pgvector', 'sqlalchemy', 'psycopg',
                                   'pydantic', 'google-genai', 'httpx')}, **(environment or {})}, cases=[],
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f'{run.run_id}.json'
    with path.open('x') as stream:
        stream.write(run.model_dump_json(indent=2) + '\n')
    try:
        with ExitStack() as resources:
            if retrieval_context is not None:
                retrieve = resources.enter_context(retrieval_context())
                run.environment.update(environment or {})
                _write(path, run.model_dump(mode='json'))
            for case in dataset.cases:
                run.cases.append(evaluate_case(case, retrieve, generator))
                _write(path, run.model_dump(mode='json'))
        run.status = 'failed' if any(c.status == 'error' for c in run.cases) else 'complete'
    except Exception as exc:
        run.status = 'failed'
        run.operation_error = {'stage': 'infrastructure', 'type': type(exc).__name__}
    finally:
        run.finished_at_utc = datetime.now(UTC)
        _write(path, run.model_dump(mode='json'))
    return path


def validate_run(run: RagRun, dataset_path: Path) -> None:
    validate_baseline(run, dataset_path)


def validate_trace(run: RagRun, dataset_path: Path) -> None:
    dataset, corpus = inputs(dataset_path)
    corpus_directory = RETRIEVAL_DIRECTORY
    if (run.status != 'complete' or run.operation_error or run.finished_at_utc is None
            or run.corpus_version != corpus['version']
            or run.corpus_sha256 != sha256(corpus_directory / 'corpus-v1.json')
            or run.freeze_sha256 != sha256(dataset_path.parent / 'freeze-v1.json')):
        raise ValueError('Incomplete run or different frozen inputs')
    from evidenceops.biomedical import BiomedicalDocument
    from evidenceops.chunking import build_retrievable_unit

    docs = {d['source_id']: d for d in corpus['documents']}
    for result in run.cases:
        if result.context is not None and bool(result.context.sources) != (result.generated is not None):
            raise ValueError('Generation trace differs from actual context path')
        if result.diagnostic:
            raise ValueError('Successful case cannot contain failure diagnostics')
        if result.error_stage is not None or result.context is None:
            raise ValueError('Missing successful context trace')
        if len(result.retrieved) > 5 or len({r.unit.unit_id for r in result.retrieved}) != len(result.retrieved):
            raise ValueError('Invalid retrieval identities')
        for retrieved in result.retrieved:
            if not isfinite(retrieved.score):
                raise ValueError('Non-finite retrieval score')
            unit = retrieved.unit
            doc = docs.get(unit.source_id)
            if doc is None:
                raise ValueError('Source outside frozen corpus')
            expected = build_retrievable_unit(BiomedicalDocument(**{
                k: v for k, v in doc.items() if k != 'area'}), publication_id=unit.publication_id)
            if unit != expected:
                raise ValueError('Source identity/content differs from frozen corpus')
        if result.context != build_context(result.retrieved):
            raise ValueError('Context trace differs from retrieved evidence')
        if result.generated is not None:
            validate_citations(result.generated, result.context.sources)
        case = next(c for c in dataset.cases if c.id == result.case_id)
        # Replay orchestration with saved retrieval/output; never invoke a provider.
        class SavedGenerator:
            def generate(self, *args, **kwargs):
                if result.generated is None:
                    raise ValueError('Missing generation')
                return result.generated
        replay = evaluate_case(case, lambda **kw: result.retrieved, SavedGenerator())
        if replay.status != 'success' or replay.output != result.output or replay.diagnostics != result.diagnostics:
            raise ValueError('Inconsistent output or diagnostic trace')


def diagnostic_summary(run: RagRun) -> dict:
    # Technical retrieval failures are excluded from quality denominators.
    retrieved = [c for c in run.cases if c.context is not None]
    with_expected = [c for c in retrieved
                     if c.diagnostics['retrieval_metrics']['recall@5'] is not None]
    return {
        'run_status': run.status, 'completed_cases': len(run.cases),
        'technical_errors': [{'case_id': c.case_id, 'stage': c.error_stage,
                              'cause': c.error, **c.diagnostic}
                             for c in run.cases if c.status == 'error'],
        'operation_error': run.operation_error,
        'retrieval_reference_coverage': aggregate_metrics([
            {'metrics': c.diagnostics['retrieval_metrics']} for c in with_expected
        ]) if with_expected else None,
        'cases_with_reference_retrieval_misses': [c.case_id for c in with_expected
                                                 if c.diagnostics['expected_not_retrieved']],
        'cases_with_reference_context_loss': [c.case_id for c in retrieved
                                              if c.diagnostics['expected_lost_from_context']],
        'abstentions': [c.case_id for c in run.cases if c.diagnostics['abstained']],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run_parser = commands.add_parser('run')
    run_parser.add_argument('--live', action='store_true')
    run_parser.add_argument('--output-dir', type=Path, default=Path('evaluation/runs/rag'))
    for name, arguments in {
        'prepare': ('run', 'destination'), 'aggregate': ('run', 'review'),
        'compare': ('baseline_run', 'baseline_review', 'candidate_run', 'candidate_review'),
        'promote': ('run', 'review', 'destination'), 'inspect': ('run',),
    }.items():
        command = commands.add_parser(name)
        for argument in arguments:
            command.add_argument(argument, type=Path)
    for command in commands.choices.values():
        command.add_argument('--dataset', type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args(argv)
    if args.command == 'run' and not args.live:
        parser.error('run requires --live; authorize provider quota and local MedCPT inference')
    try:
        if args.command == 'run':
            dataset, corpus = inputs(args.dataset)
            settings = Settings()
            key = settings.gemini_api_key if settings.llm_provider == 'gemini' else settings.deepseek_api_key
            if key is None:
                raise ValueError('Missing selected provider key')
            from evidenceops.embeddings import LocalMedCPT
            from evidenceops.generator_factory import create_generator
            encoder = LocalMedCPT()
            environment = {'device': 'cpu', 'dtype': 'float32'}
            from contextlib import contextmanager

            @contextmanager
            def retrieval_context():
                with frozen_sessions(corpus, str(settings.database_url), encoder, environment) as sessions:
                    import torch
                    environment.update(torch_threads=torch.get_num_threads(),
                                       torch_interop_threads=torch.get_num_interop_threads())
                    yield partial(search, sessions, encoder)

            with closing(create_generator(settings)) as generator:
                path = run_evaluation(generator, None,
                    dataset_path=args.dataset, settings=settings, encoder_configuration=encoder.config.metadata(),
                    output_dir=args.output_dir, environment=environment, retrieval_context=retrieval_context)
            print(path)
            return int(RagRun.model_validate_json(path.read_bytes()).status != 'complete')

        def load_run(path):
            run = RagRun.model_validate_json(path.read_bytes())
            validate_run(run, args.dataset)
            return run

        def load_review(path):
            return human.Review.model_validate_json(path.read_bytes())

        if args.command == 'inspect':
            # Failed/incomplete runs remain inspectable, but cannot be promoted/reviewed.
            run = RagRun.model_validate_json(args.run.read_bytes())
            report = {**diagnostic_summary(run), 'cases': [dict(case_id=c.case_id, status=c.status,
                      error=c.error, error_stage=c.error_stage, diagnostic=c.diagnostic,
                      **c.diagnostics) for c in run.cases]}
        elif args.command == 'prepare':
            review = human.prepare_review(load_run(args.run), args.dataset)
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            with args.destination.open('x') as stream:
                stream.write(review.model_dump_json(indent=2) + '\n')
            print(args.destination)
            return 0
        elif args.command == 'aggregate':
            run = load_run(args.run)
            report = human.aggregate(load_review(args.review), run, args.dataset)
            report['pipeline'] = diagnostic_summary(run)
        elif args.command == 'compare':
            baseline_run, candidate_run = load_run(args.baseline_run), load_run(args.candidate_run)
            report = human.compare(load_review(args.baseline_review), baseline_run,
                                   load_review(args.candidate_review), candidate_run, args.dataset)
            report['pipeline'] = {'baseline': diagnostic_summary(baseline_run),
                                  'candidate': diagnostic_summary(candidate_run)}
            report['diagnostics_by_case'] = [
                {'case_id': before.case_id, 'baseline': before.diagnostics, 'candidate': after.diagnostics}
                for before, after in zip(baseline_run.cases, candidate_run.cases, strict=True)
            ]
            report['configuration'] = {
                'baseline': dict(provider=baseline_run.provider, model=baseline_run.model,
                                 **baseline_run.configuration),
                'candidate': dict(provider=candidate_run.provider, model=candidate_run.model,
                                  **candidate_run.configuration),
            }
        else:
            run, review = load_run(args.run), load_review(args.review)
            human.validate_review(review, run, args.dataset)
            destination_review = args.destination.with_suffix('.review.json')
            if args.destination.exists() or destination_review.exists() or args.destination == destination_review:
                raise ValueError('Baseline destination already exists or is ambiguous')
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            with args.destination.open('xb') as stream:
                stream.write(args.run.read_bytes())
            with destination_review.open('xb') as stream:
                stream.write(args.review.read_bytes())
            print(args.destination)
            return 0
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return int(args.command == 'compare' and bool(report['regressions']))
    except Exception:
        parser.exit(2, 'Invalid RAG evaluation inputs or operation failed; check configuration, '
                    'completeness, frozen hashes, traces and human verdicts.\n')


if __name__ == '__main__':
    raise SystemExit(main())

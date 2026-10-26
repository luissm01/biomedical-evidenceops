"""Fixed-corpus retrieval evaluation, independent of generator evaluation."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import subprocess
from statistics import mean, median
from math import ceil
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictStr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from evidenceops.biomedical import BiomedicalDocument
from evidenceops.config import Settings
from evidenceops.embeddings import LocalMedCPT
from evidenceops.lexical import BM25_K1, BM25_B, RRF_K, TOKENIZER
from evidenceops.models import Base, Publication, UnitEmbedding
from evidenceops.publications import upsert_publication
from evidenceops.retrieval import index_publication, search
from evidenceops.reranking import LocalMedCPTReranker, RERANK_CANDIDATES

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIRECTORY = ROOT / 'evaluation' / 'retrieval'


class Relevant(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    pmid: StrictStr = Field(pattern=r'^\d+$')
    reason: StrictStr = Field(min_length=1)


class Query(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: StrictStr = Field(min_length=1)
    query: StrictStr = Field(min_length=1)
    criterion: StrictStr = Field(min_length=1)
    relevant: list[Relevant]
    ambiguous: list[Relevant]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs(directory: Path) -> tuple[dict, dict, list[Query]]:
    """Require the exact frozen corpus and pre-retrieval judgments."""
    corpus = json.loads((directory / 'corpus-v1.json').read_text())
    dataset = json.loads((directory / 'queries-v1.json').read_text())
    frozen = json.loads((directory / 'freeze-v1.json').read_text())
    for filename in ('corpus-v1.json', 'queries-v1.json'):
        if sha256(directory / filename) != frozen['sha256'][filename]:
            raise ValueError(f'Frozen input changed: {filename}; create a new version')
    if dataset['corpus_version'] != corpus['version'] or dataset['judgments']['coverage'] != 'all-query-publication-pairs':
        raise ValueError('Dataset must refer to this corpus with exhaustive judgments')
    docs = corpus['documents']
    ids = [doc['source_id'] for doc in docs]
    if not ids or len(ids) != len(set(ids)) or any(
        doc['source'] != 'pubmed' or not doc['source_id'].isdecimal()
        or not doc['title'].strip() or not doc['abstract'] or not doc['abstract'].strip()
        for doc in docs
    ):
        raise ValueError('Corpus requires unique PubMed identities with title and abstract')
    queries = [Query.model_validate(query) for query in dataset['queries']]
    if not queries or len({query.id for query in queries}) != len(queries):
        raise ValueError('Query IDs must be unique and nonempty')
    for query in queries:
        judged = [item.pmid for item in query.relevant + query.ambiguous]
        if not query.query.strip() or len(judged) != len(set(judged)) or not set(judged) <= set(ids):
            raise ValueError('Judgments must be distinct corpus publications and query nonblank')
    return corpus, dataset, queries


def publication_metrics(ranking: list[str], relevant: set[str], *, k: int = 5) -> dict:
    """Binary publication metrics. MRR uses the entire supplied ranking.

    Precision divides by requested K even for short rankings. No relevant:
    recall is undefined (None); hit, precision and reciprocal rank are zero.
    Reject duplicate publications rather than count multiple chunks as hits.
    """
    if type(k) is not int or k <= 0:
        raise ValueError('k must be a positive integer')
    if len(ranking) != len(set(ranking)):
        raise ValueError('Ranking contains duplicate publications')
    hits = len(set(ranking[:k]) & relevant)
    first = next((i for i, pmid in enumerate(ranking, 1) if pmid in relevant), None)
    return {
        f'hit_rate@{k}': float(hits > 0),
        f'recall@{k}': hits / len(relevant) if relevant else None,
        f'precision@{k}': hits / k,
        'reciprocal_rank': 1 / first if first else 0.0,
    }


def aggregate_metrics(results: list[dict], *, k: int = 5) -> dict:
    if not results:
        raise ValueError('Cannot aggregate zero queries')
    output = {}
    for metric in (f'hit_rate@{k}', f'recall@{k}', f'precision@{k}', 'reciprocal_rank'):
        values = [r['metrics'][metric] for r in results if r['metrics'][metric] is not None]
        output['mrr' if metric == 'reciprocal_rank' else metric] = sum(values) / len(values) if values else None
    output['queries'] = len(results)
    output['queries_with_relevants'] = sum(r['metrics'][f'recall@{k}'] is not None for r in results)
    return output


class CachedQueryEncoder:
    """Reuse one query vector for top-5 and full diagnostic ranking."""
    def __init__(self, encoder):
        self.encoder = encoder
        self.config = encoder.config
        self.queries = {}

    def encode_query(self, query):
        if query not in self.queries:
            self.queries[query] = self.encoder.encode_query(query)
        return self.queries[query]


def aggregate_latency(results: list[dict]) -> dict:
    """Descriptive seconds, nearest-rank p95; a small sample is not a benchmark."""
    return {stage: {
        'mean': mean(values), 'median': median(values),
        'p95': sorted(values)[ceil(.95 * len(values)) - 1],
    } for stage in ('retrieval_seconds', 'reranker_seconds', 'total_seconds')
       for values in [[row['latency'][stage] for row in results]]}


def evaluate(sessions, encoder, queries: list[Query], corpus_size: int, checkpoint=None, *,
             mode="semantic", reranker=None, warmup=False) -> list[dict]:
    if warmup:
        search(sessions, encoder, query=queries[0].query, top_k=5, mode=mode, reranker=reranker)
    results = []
    for query in queries:
        cached = CachedQueryEncoder(encoder)
        latency = {}
        top = search(sessions, cached, query=query.query,
                     top_k=RERANK_CANDIDATES if mode == 'reranking' else 5,
                     mode=mode, candidate_k=corpus_size, reranker=reranker, timings=latency)
        # Diagnostic query is outside measured serving latency, reuses query vector.
        full = search(sessions, cached, query=query.query, top_k=corpus_size,
                      mode='semantic' if mode == 'reranking' else mode, candidate_k=corpus_size)
        candidates = []
        if mode == 'reranking':
            candidates = full[:RERANK_CANDIDATES]
            if {r.unit.unit_id for r in top} != {r.unit.unit_id for r in candidates}:
                raise ValueError('Reranked candidates differ from semantic top 20')
            full = top + full[RERANK_CANDIDATES:]
        pmids = [r.unit.source_id for r in full]
        if len(full) != corpus_size or [r.unit.source_id for r in top[:5]] != pmids[:5]:
            raise ValueError('Retriever did not return the exact frozen corpus ranking')
        relevant = {item.pmid for item in query.relevant}
        results.append({
            'query_id': query.id, 'query': query.query,
            'metrics': publication_metrics(pmids, relevant),
            'top_5': pmids[:5], 'latency': latency,
            'ranking': [
                {'rank': i, 'pmid': r.unit.source_id, 'unit_id': r.unit.unit_id,
                 'content_fingerprint': r.unit.content_fingerprint,
                 'score': r.score, 'relevant': r.unit.source_id in relevant}
                for i, r in enumerate(full, 1)
            ],
        })
        if mode == 'reranking':
            for record, result in zip(results[-1]['ranking'], full, strict=True):
                original_score = getattr(result, 'retrieval_score', None)
                record.update(
                    retrieval_score=result.score if original_score is None else original_score,
                    reranker_score=None if original_score is None else result.score,
                    score_type='semantic-dot-product' if original_score is None else 'cross-encoder-logit',
                )
            results[-1]['candidates'] = [
                {'rank': i, 'pmid': r.unit.source_id, 'unit_id': r.unit.unit_id,
                 'content_fingerprint': r.unit.content_fingerprint, 'score': r.score}
                for i, r in enumerate(candidates, 1)
            ]
        if checkpoint:
            checkpoint(results)
    return results


def _write(path: Path, run: dict) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(run, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


@contextmanager
def frozen_sessions(corpus: dict, database_url: str, encoder, environment: dict):
    """Index the frozen corpus in a private schema; always release owned resources."""
    schema = 'retrieval_eval_' + uuid4().hex
    admin = create_engine(database_url)
    engine = None
    created = False
    try:
        with admin.begin() as connection:
            environment['postgresql'] = connection.scalar(text('SHOW server_version'))
            environment['pgvector_extension'] = connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
            if environment['pgvector_extension'] is None:
                raise ValueError('Install pgvector with the project migrations before evaluation')
            connection.execute(text(f'CREATE SCHEMA {schema}'))
            created = True
        # Only this private schema contains evaluation tables; public resolves vector.
        engine = create_engine(database_url, connect_args={'options': f'-csearch_path={schema},public'})
        Base.metadata.create_all(engine, tables=[Publication.__table__, UnitEmbedding.__table__], checkfirst=False)
        sessions = sessionmaker(engine, expire_on_commit=False)
        ids = []
        with sessions.begin() as session:
            for doc in corpus['documents']:
                document = BiomedicalDocument(**{key: value for key, value in doc.items() if key != 'area'})
                ids.append(upsert_publication(session, document).id)
        for i, publication_id in enumerate(ids, 1):
            index_publication(sessions, publication_id, encoder)
            print(f'Indexed {i}/{len(ids)}', flush=True)
        yield sessions
    finally:
        if engine is not None:
            engine.dispose()
        try:
            if created:
                with admin.begin() as connection:
                    connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        finally:
            admin.dispose()


def run_baseline(directory: Path, output: Path, database_url: str, encoder, *,
                 mode="semantic", reranker=None, warmup=False) -> dict:
    corpus, dataset, queries = load_inputs(directory)  # Always before inference.
    if mode not in ("semantic", "hybrid", "reranking"):
        raise ValueError("mode must be semantic, hybrid or reranking")
    if mode == "reranking" and reranker is None:
        raise ValueError("reranking requires a MedCPT reranker")
    run = {
        'run_version': '1', 'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'corpus_version': corpus['version'], 'dataset_version': dataset['version'],
        'input_sha256': {name: sha256(directory / name) for name in ('corpus-v1.json', 'queries-v1.json', 'freeze-v1.json')},
        'configuration': {**encoder.config.metadata(), 'top_k': 5, 'published_from': None,
                          'mode': mode, 'ranking': {'semantic': 'exact-pgvector', 'hybrid': 'bm25-pgvector-rrf',
                                                    'reranking': 'semantic-top20-cross-encoder-then-semantic-tail'}[mode], 'tie_break': 'unit_id ascending', 'mrr_depth': len(corpus['documents'])},
        'code': {
            'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'working_tree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)),
            'source_sha256': {str(path.relative_to(ROOT)): sha256(path) for path in (ROOT / 'src' / 'evidenceops').glob('*.py')},
        },
        'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                        'machine': platform.machine(), 'processor': platform.processor(),
                        'packages': {name: package_version(name) for name in ('evidenceops', 'torch', 'transformers', 'pgvector', 'sqlalchemy', 'psycopg')}},
        'results': [],
    }
    if mode == 'hybrid':
        run['configuration']['hybrid'] = {
            'bm25_k1': BM25_K1, 'bm25_b': BM25_B, 'tokenizer': TOKENIZER,
            'query_terms': 'unique', 'statistics': 'eligible-corpus',
            'lexical_candidates': 'positive-score-only', 'rrf_k': RRF_K,
            'candidate_k': len(corpus['documents']),
        }
    run['configuration']['latency'] = {
        'clock': 'perf_counter', 'unit': 'seconds', 'warmup_queries': int(warmup),
        'retrieval': 'query-encoding-and-sql-and-unit-validation',
        'reranker': 'tokenization-forward-scoring-and-ordering; lazy-load-if-cold',
        'total': 'serving-path; excludes indexing, warmup, diagnostic ranking and metrics',
        'query_vector_cache': 'empty for each measured query; diagnostic reads reuse vector',
    }
    if mode == 'reranking':
        run['configuration']['reranker'] = {**reranker.config.metadata(), 'candidate_k': RERANK_CANDIDATES}
    if isinstance(encoder, LocalMedCPT):
        import torch
        run['environment']['torch_threads'] = torch.get_num_threads()
        run['environment']['torch_interop_threads'] = torch.get_num_interop_threads()
        run['environment']['device'] = 'cpu'
        run['environment']['dtype'] = 'float32'
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as file:
        file.write(json.dumps(run, indent=2) + '\n')
    try:
        with frozen_sessions(corpus, database_url, encoder, run['environment']) as sessions:
            def checkpoint(results):
                run['results'] = results
                _write(output, run)
            run['results'] = evaluate(sessions, encoder, queries, len(corpus['documents']), checkpoint, mode=mode, reranker=reranker, warmup=warmup)
            run['aggregate'] = aggregate_metrics(run['results'])
            run['latency'] = aggregate_latency(run['results'])
            run['status'] = 'complete'
    except Exception as exc:
        run['status'] = 'failed'
        run['error_type'] = type(exc).__name__  # No URLs, credentials or raw exception messages.
        raise
    finally:
        run['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        _write(output, run)
    return run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('semantic', 'hybrid', 'reranking'), default='semantic')
    parser.add_argument('--live', action='store_true', help='Authorize local MedCPT inference and model downloads')
    parser.add_argument('--warmup', action='store_true', help='One unmeasured query to warm model/tokenizer/DB caches')
    parser.add_argument('--dataset-dir', type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument('--output', type=Path, required=True, help='New JSON path; never overwrite')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required; tests never perform model inference')
    run = run_baseline(args.dataset_dir, args.output, str(Settings().database_url), LocalMedCPT(), mode=args.mode,
                       reranker=LocalMedCPTReranker() if args.mode == 'reranking' else None, warmup=args.warmup)
    print(json.dumps(run['aggregate'], indent=2))


if __name__ == '__main__':
    main()

import json
import logging
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import delete, event, func, select
from sqlalchemy.exc import SQLAlchemyError

from evidenceops import ingestion, ingestion_cli
from evidenceops.config import PubMedSettings
from evidenceops.database import create_database
from evidenceops.models import Publication
from evidenceops.observability import JsonFormatter
from evidenceops.pubmed import PubMedClient


@pytest.fixture(autouse=True)
def restore_logging():
    logger = logging.getLogger('evidenceops')
    handlers, level, propagate = list(logger.handlers), logger.level, logger.propagate
    yield
    for handler in logger.handlers:
        if handler not in handlers:
            handler.close()
    logger.handlers = handlers
    logger.setLevel(level)
    logger.propagate = propagate


@pytest.fixture
def sessions(test_settings, migrated_database):
    engine, factory = create_database(test_settings)
    with factory.begin() as session:
        session.execute(delete(Publication))
    try:
        yield engine, factory
    finally:
        with factory.begin() as session:
            session.execute(delete(Publication))
        engine.dispose()


def xml_for(ids):
    articles = ''.join(
        f'<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article>'
        f'<ArticleTitle>Title {pmid}</ArticleTitle></Article></MedlineCitation></PubmedArticle>'
        for pmid in ids
    )
    return f'<PubmedArticleSet>{articles}</PubmedArticleSet>'.encode()


@contextmanager
def pubmed(handler):
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with PubMedClient(PubMedSettings(_env_file=None), http_client=http, sleep=lambda _: None) as client:
            yield client


def test_end_to_end_reingestion_deduplication_and_single_statement(sessions):
    engine, factory = sessions
    fixture = (Path(__file__).parent / 'fixtures/pubmed_articles.xml').read_bytes()
    statements = []
    def capture(_conn, _cursor, statement, *_args):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', capture)
    with pubmed(lambda _: httpx.Response(200, content=fixture)) as client:
        first = ingestion.ingest_pubmed(client, factory, pmids=['12345', '67890', '12345'])
        second = ingestion.ingest_pubmed(client, factory, pmids=['12345', '67890'])
    event.remove(engine, 'before_cursor_execute', capture)
    assert (first.created, first.updated, first.omitted, first.failed) == (2, 0, 1, 0)
    assert (first.requested, first.unique, first.batches) == (3, 2, 1)
    assert (second.created, second.updated, second.failed) == (0, 2, 0)
    assert len(statements) == 4
    assert all('INSERT INTO publications' in sql and 'ON CONFLICT' in sql for sql in statements)
    with factory() as session:
        rows = session.scalars(select(Publication).order_by(Publication.source_id)).all()
        assert len(rows) == 2
        assert rows[0].authors == ['Ana María García', 'Evidence Study Group', 'J Lee Jr']
        assert rows[0].abstract.startswith('BACKGROUND:')
        assert rows[1].abstract is None


def test_invalid_missing_and_unidentified_records_allow_valid_documents(sessions):
    _, factory = sessions
    fixture = (Path(__file__).parent / 'fixtures/pubmed_partial.xml').read_bytes()
    # A malformed identifier must not invalidate the valid article's batch.
    fixture = fixture.replace(b'<MedlineCitation><Article>', b'<MedlineCitation><PMID>bad</PMID><Article>')
    with pubmed(lambda _: httpx.Response(200, content=fixture)) as client:
        result = ingestion.ingest_pubmed(client, factory, pmids=['12345', '67890', '99999'])
    assert (result.created, result.failed, result.unidentified_invalid) == (1, 3, 1)
    assert {item.source_id for item in result.failures} == {'67890', '99999', None}
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Publication)) == 1


@pytest.mark.parametrize('bad_response', ['http', 'xml', 'timeout'])
def test_failed_external_batch_does_not_stop_later_batches(sessions, bad_response):
    _, factory = sessions
    sizes = []
    def respond(request):
        ids = parse_qs(request.content.decode())['id'][0].split(',')
        sizes.append(len(ids))
        if len(sizes) == 1:
            if bad_response == 'timeout':
                raise httpx.ReadTimeout('secret response', request=request)
            return httpx.Response(503) if bad_response == 'http' else httpx.Response(200, content=b'<broken')
        return httpx.Response(200, content=xml_for(ids))
    with pubmed(respond) as client:
        result = ingestion.ingest_pubmed(client, factory, pmids=list(map(str, range(1, 202))))
    assert sizes == [200, 1]
    assert (result.created, result.failed, result.batches) == (1, 200, 2)
    assert [f.source_id for f in result.failures] == list(map(str, range(1, 201)))


def test_persistence_failure_rolls_back_only_affected_document(sessions, monkeypatch):
    _, factory = sessions
    original = ingestion.upsert_publication
    def write(session, document, **kwargs):
        row = original(session, document, **kwargs)
        if document.source_id == '2':
            raise SQLAlchemyError('secret content')
        return row
    monkeypatch.setattr(ingestion, 'upsert_publication', write)
    with pubmed(lambda _: httpx.Response(200, content=xml_for(['1', '2', '3']))) as client:
        result = ingestion.ingest_pubmed(client, factory, pmids=['1', '2', '3'])
    assert (result.created, result.failed) == (2, 1)
    assert result.failures[0].cause == 'persistence_error'
    with factory() as session:
        assert session.scalars(select(Publication.source_id).order_by(Publication.source_id)).all() == ['1', '3']


def test_commit_failure_is_not_counted_as_success(sessions, monkeypatch):
    _, factory = sessions
    real_begin = factory.begin
    @contextmanager
    def failing_commit():
        with real_begin() as session:
            yield session
            raise SQLAlchemyError('commit failure')
    monkeypatch.setattr(factory, 'begin', failing_commit)
    with pubmed(lambda _: httpx.Response(200, content=xml_for(['1']))) as client:
        result = ingestion.ingest_pubmed(client, factory, pmids=['1'])
    assert (result.created, result.updated, result.failed) == (0, 0, 1)
    monkeypatch.setattr(factory, 'begin', real_begin)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Publication)) == 0


@pytest.mark.parametrize('response,expected', [(b'<eSearchResult><IdList /></eSearchResult>', 0), (b'<broken', 1)])
def test_search_empty_and_failure(sessions, response, expected):
    _, factory = sessions
    with pubmed(lambda _: httpx.Response(200, content=response)) as client:
        result = ingestion.ingest_pubmed(client, factory, query='test', limit=2)
    assert result.failed == expected
    assert (result.requested, result.created, result.batches) == (0, 0, 0)


def test_cli_query_end_to_end_and_safe_structured_logs(sessions, monkeypatch, capsys):
    engine, factory = sessions
    requests = []
    def respond(request):
        requests.append(request)
        if request.method == 'GET':
            return httpx.Response(200, content=b'<eSearchResult><IdList><Id>1</Id><Id>1</Id></IdList></eSearchResult>')
        return httpx.Response(200, content=xml_for(['1']))
    events = []
    class Capture(logging.Handler):
        def emit(self, record):
            events.append(json.loads(JsonFormatter().format(record)))
    handler = Capture()
    logger = logging.getLogger('evidenceops')
    logger.addHandler(handler)
    with pubmed(respond) as client:
        monkeypatch.setattr(ingestion_cli, 'PubMedClient', lambda _: client)
        monkeypatch.setattr(ingestion_cli, 'create_database', lambda _: (engine, factory))
        try:
            assert ingestion_cli.main(['ingest', '--query', 'private query', '--limit', '2']) == 0
        finally:
            logger.removeHandler(handler)
    output = capsys.readouterr().out
    summary = json.loads(output.splitlines()[-1])
    assert (summary['created'], summary['omitted']) == (1, 1)
    assert len(requests) == 2
    assert [e['event'] for e in events] == ['ingestion.started', 'ingestion.finished']
    assert events[-1]['created'] == 1 and events[-1]['duration_ms'] >= 0
    assert events[0]['run_id'] == events[-1]['run_id']
    assert 'private query' not in output and 'Title 1' not in output


def test_cli_explicit_pmids_partial_failure_exit_code(sessions, monkeypatch, capsys):
    engine, factory = sessions
    with pubmed(lambda _: httpx.Response(200, content=xml_for(['1']))) as client:
        monkeypatch.setattr(ingestion_cli, 'PubMedClient', lambda _: client)
        monkeypatch.setattr(ingestion_cli, 'create_database', lambda _: (engine, factory))
        assert ingestion_cli.main(['ingest', '--pmid', '1', '2', '--pmid', '1']) == 1
    summary = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert (summary['created'], summary['omitted'], summary['failed']) == (1, 1, 1)


@pytest.mark.parametrize('args', [[], ['ingest'], ['ingest', '--pmid', 'bad'],
    ['ingest', '--pmid', '1', '--query', 'q', '--limit', '1'],
    ['ingest', '--query', 'q'], ['ingest', '--query', ' ', '--limit', '1'],
    ['ingest', '--query', 'q', '--limit', '101'], ['ingest', '--pmid', '1', '--limit', '1']])
def test_cli_invalid_arguments_create_no_resources(args, monkeypatch):
    monkeypatch.setattr(ingestion_cli, 'create_database', lambda _: pytest.fail('unexpected database'))
    monkeypatch.setattr(ingestion_cli, 'PubMedClient', lambda _: pytest.fail('unexpected network'))
    with pytest.raises(SystemExit) as exc:
        ingestion_cli.main(args)
    assert exc.value.code == 2


def test_concurrent_reingestion_classifies_one_create_and_one_update(sessions):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    _, factory = sessions
    ready = Barrier(2)
    def run():
        with pubmed(lambda _: httpx.Response(200, content=xml_for(['1']))) as client:
            ready.wait(timeout=5)
            return ingestion.ingest_pubmed(client, factory, pmids=['1'])
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run(), range(2)))
    assert sum(r.created for r in results) == 1
    assert sum(r.updated for r in results) == 1
    assert sum(r.failed for r in results) == 0
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Publication)) == 1


def test_cli_search_failure_has_safe_summary_and_nonzero_exit(sessions, monkeypatch, capsys):
    engine, factory = sessions
    with pubmed(lambda _: httpx.Response(503, text='private provider body')) as client:
        monkeypatch.setattr(ingestion_cli, 'PubMedClient', lambda _: client)
        monkeypatch.setattr(ingestion_cli, 'create_database', lambda _: (engine, factory))
        assert ingestion_cli.main(['ingest', '--query', 'q', '--limit', '1']) == 1
    output = capsys.readouterr().out
    result = json.loads(output.splitlines()[-1])
    assert result['failed'] == 1 and result['requested'] == 0
    assert result['failures'] == [{'source_id': None, 'cause': 'search_http_error'}]
    assert 'private provider body' not in output


def test_cli_setup_failure_is_safe(monkeypatch, capsys):
    def fail(_settings):
        raise SQLAlchemyError('secret connection details')
    monkeypatch.setattr(ingestion_cli, 'create_database', fail)
    assert ingestion_cli.main(['ingest', '--pmid', '1']) == 1
    output = capsys.readouterr().err
    assert 'configuration_or_database_error' in output
    assert 'secret connection details' not in output


@pytest.mark.parametrize('kwargs', [
    {}, {'pmids': []}, {'pmids': ['bad']}, {'pmids': ['1'], 'limit': 1},
    {'pmids': ['1'], 'query': 'q', 'limit': 1}, {'query': 'q'},
    {'query': ' ', 'limit': 1}, {'query': 'q', 'limit': 0},
])
def test_service_rejects_invalid_input_before_io(kwargs):
    ingestion_client = object()
    with pytest.raises(ValueError):
        ingestion.ingest_pubmed(ingestion_client, None, **kwargs)

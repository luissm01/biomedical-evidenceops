"""Actual PostgreSQL/pgvector; deterministic MedCPT and LLM, no remote inference."""

from contextlib import contextmanager
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import delete, text

from evidenceops.database import create_database
from evidenceops.generation import GeneratedContent
from evidenceops.models import Publication
from evidenceops.rag import ABSTENTION_ANSWER
from evidenceops.retrieval import index_publication
from evidenceops.tool_calling import ToolCallingService, ToolProposal
from evidenceops.tools import ToolCallingError, create_tool_executor
from test_retrieval import ControlledMedCPT, document, persist
from test_tools import call


@pytest.fixture
def database(test_settings, migrated_database):
    engine, sessions = create_database(test_settings)
    try:
        yield sessions
    finally:
        engine.dispose()


def test_existing_retrieval_lookup_filters_and_no_writes(database):
    sessions = database
    encoder = ControlledMedCPT()
    ids = []
    try:
        publication_id = persist(sessions, document(source_id=f"tools-{uuid4()}", year=2024))
        ids.append(publication_id)
        index_publication(sessions, publication_id, encoder)
        executor = create_tool_executor(sessions, encoder)
        model = Mock()
        model.propose.return_value = ToolProposal(call(arguments={"query": "discovery", "top_k": 5, "published_from": 2024}))
        def finalize(*args):
            assert sessions.kw["bind"].pool.checkedout() == 0  # No connection held while waiting for LLM.
            return GeneratedContent(answer="Candidata [S1].", limitations=[])
        model.finalize.side_effect = finalize
        response = ToolCallingService(model, executor).run("discovery")
        assert any(source.publication_id == publication_id for source in response.sources)
        assert all(source.publication_year >= 2024 for source in response.sources)
        assert encoder.query_calls == ["discovery"]
        assert "abstract" not in response.tool_result.payload()["data"]["items"][0]
        detail = executor.execute(call("get_publication", {"publication_id": str(publication_id)}))
        assert detail.data.abstract == "Treatment evidence"
        assert detail.data.authors == ["Study Group"]
        assert detail.data.publication_id == publication_id
        assert executor.execute(call("get_publication", {"publication_id": str(uuid4())})).error.code == "publication_not_found"
        assert executor.execute(call(arguments={"query": "discovery", "published_from": 9999})).data.items == []
        with sessions() as session:
            persisted = session.get(Publication, publication_id)
            assert persisted.abstract == "Treatment evidence" and persisted.publication_year == 2024
        assert len(encoder.article_calls) == 1  # No indexing/ingestion from tool execution.
    finally:
        with sessions.begin() as session:
            session.execute(delete(Publication).where(Publication.id.in_(ids)))


def test_sql_timeout_is_effective_and_does_not_leak_session_setting(database, monkeypatch):
    sessions = database
    monkeypatch.setattr("evidenceops.tools.SQL_TIMEOUT_MS", 1)
    @contextmanager
    def delayed_sessions():
        with sessions() as session:
            # Executed inside get_publication, after the SQL timeout is installed.
            session.get = lambda *args: session.execute(text("SELECT pg_sleep(0.03)"))
            yield session
    executor = create_tool_executor(delayed_sessions, ControlledMedCPT())
    with pytest.raises(ToolCallingError, match="sql_timeout"):
        executor.execute(call("get_publication", {"publication_id": str(uuid4())}))
    with sessions() as session:
        assert session.scalar(text("SHOW statement_timeout")) != "1ms"


def test_tool_transaction_is_read_only(database):
    sessions = database
    @contextmanager
    def writing_sessions():
        with sessions() as session:
            session.get = lambda *args: session.execute(text("DELETE FROM publications WHERE false"))
            yield session
    executor = create_tool_executor(writing_sessions, ControlledMedCPT())
    with pytest.raises(ToolCallingError, match="backend_error") as caught:
        executor.execute(call("get_publication", {"publication_id": str(uuid4())}))
    assert caught.value.__cause__.orig.sqlstate == "25006"


@pytest.mark.parametrize("scenario,code,requests", [
    ("search", None, 2), ("publication", None, 2), ("empty", None, 2),
    ("not-found", None, 2), ("invalid", "invalid_arguments", 1),
    ("unknown", "unknown_tool", 1), ("second-round", "round_limit_exceeded", 2),
    ("backend-error", "backend_error", 1),
])
def test_offline_demo(scenario, code, requests):
    from evidenceops.tool_calling_demo import run_demo
    result = run_demo(scenario)
    assert result["simulated_requests"] == requests
    if code:
        assert result["status"] == "error" and result["code"] == code
    else:
        assert result["status"] == "ok"
        if scenario in {"empty", "not-found"}:
            assert result["answer"] == ABSTENTION_ANSWER and result["sources"] == []

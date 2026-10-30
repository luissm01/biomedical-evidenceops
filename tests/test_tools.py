"""Deterministic tool contracts and controlled backend execution."""

import json
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy.exc import DBAPIError

from evidenceops.chunking import build_retrievable_unit
from evidenceops.retrieval import RetrievalResult
from evidenceops.tools import (
    ARGUMENT_CHARACTER_LIMIT, RESULT_CHARACTER_LIMIT, TOOL_BUDGET_SECONDS,
    TOOL_DEFINITIONS, ToolCall, ToolCallingError, ToolExecutor, compact_json,
)
from test_retrieval import document

PUBLICATION_ID = UUID("123e4567-e89b-42d3-a456-426614174000")


def call(name="search_evidence", arguments=None):
    return ToolCall(id="call_1", name=name, arguments=json.dumps(
        {"query": "discovery"} if arguments is None else arguments))


@pytest.fixture
def backends():
    doc = document(abstract="complete abstract, not for discovery")
    unit = build_retrievable_unit(doc, publication_id=PUBLICATION_ID)
    retrieve = Mock(return_value=[RetrievalResult(unit, 0.5)])
    lookup = Mock(return_value=doc)
    return retrieve, lookup


def test_discovery_is_compact_and_preserves_identity_without_abstract(backends):
    retrieve, lookup = backends
    result = ToolExecutor(*backends).execute(call(arguments={"query": " discovery ", "top_k": 2, "published_from": 2020}))
    retrieve.assert_called_once_with(query="discovery", top_k=2, published_from=2020)
    lookup.assert_not_called()
    payload = result.payload()
    hit = payload["data"]["items"][0]
    assert hit["publication_id"] == str(PUBLICATION_ID)
    assert hit["source"] == "pubmed" and hit["source_id"] == "1"
    assert hit["citation_id"] == "S1" and hit["detail_level"] == "metadata"
    assert hit["unit_id"] and hit["content_fingerprint"] and hit["score"] == .5
    assert "abstract" not in hit and "text" not in hit and "authors" not in hit
    assert "complete abstract" not in compact_json(payload)
    assert result.call_id == "call_1" and result.status == "ok"


def test_publication_returns_full_details_and_missing_fields_as_null(backends):
    retrieve, lookup = backends
    executor = ToolExecutor(*backends)
    result = executor.execute(call("get_publication", {"publication_id": str(PUBLICATION_ID)}))
    lookup.assert_called_once_with(PUBLICATION_ID)
    retrieve.assert_not_called()
    detail = result.payload()["data"]
    assert detail["abstract"] == "complete abstract, not for discovery"
    assert detail["authors"] == ["Study Group"]
    assert detail["citation_id"] == "S1" and detail["detail_level"] == "abstract"
    lookup.return_value = document(abstract=None)
    assert executor.execute(call("get_publication", {"publication_id": str(PUBLICATION_ID)})).payload()["data"]["abstract"] is None


def test_empty_search_and_missing_publication_are_distinct(backends):
    retrieve, lookup = backends
    retrieve.return_value = []
    lookup.return_value = None
    executor = ToolExecutor(*backends)
    empty = executor.execute(call())
    missing = executor.execute(call("get_publication", {"publication_id": str(PUBLICATION_ID)}))
    assert empty.status == "ok" and empty.payload()["data"] == {"items": []}
    assert missing.status == "error" and missing.error.code == "publication_not_found"
    assert empty.sources() == missing.sources() == ()


@pytest.mark.parametrize("arguments", [
    {}, {"query": " "}, {"query": 3}, {"query": "x" * 2001},
    {"query": "x", "top_k": True}, {"query": "x", "top_k": "2"},
    {"query": "x", "top_k": 0}, {"query": "x", "top_k": 6},
    {"query": "x", "published_from": "2020"}, {"query": "x", "published_from": False},
    {"query": "x", "published_from": 0}, {"query": "x", "mode": "hybrid"},
    [], None, "string",
])
def test_invalid_search_arguments_never_access_backend(backends, arguments):
    invocation = ToolCall(id="call_1", name="search_evidence", arguments=json.dumps(arguments))
    with pytest.raises(ToolCallingError, match="invalid_arguments"):
        ToolExecutor(*backends).execute(invocation)
    for backend in backends:
        backend.assert_not_called()


@pytest.mark.parametrize("raw", ['{broken', '{"query":"x","query":"y"}', '{"query":NaN}', '[]', '[' * 2000])
def test_invalid_raw_json(backends, raw):
    with pytest.raises(ToolCallingError, match="invalid_arguments"):
        ToolExecutor(*backends).execute(ToolCall(id="call_1", name="search_evidence", arguments=raw))
    assert not any(backend.called for backend in backends)


@pytest.mark.parametrize("arguments", [{"publication_id": "not-uuid"}, {"publication_id": 12}, {},
    {"publication_id": str(PUBLICATION_ID), "source_id": "1"}])
def test_invalid_publication_arguments(backends, arguments):
    with pytest.raises(ToolCallingError, match="invalid_arguments"):
        ToolExecutor(*backends).execute(call("get_publication", arguments))
    assert not any(backend.called for backend in backends)


def test_unknown_tool_is_rejected(backends):
    with pytest.raises(ToolCallingError, match="unknown_tool"):
        ToolExecutor(*backends).execute(call("ingest_publication"))
    assert not any(backend.called for backend in backends)
    assert {item.name for item in TOOL_DEFINITIONS} == {"search_evidence", "get_publication"}
    assert all(item.arguments.model_json_schema()["additionalProperties"] is False for item in TOOL_DEFINITIONS)


def test_exact_argument_and_output_size_limits(backends, monkeypatch):
    executor = ToolExecutor(*backends)
    raw = '{"query":"x"}'
    invocation = ToolCall(id="call_1", name="search_evidence", arguments=raw + ' ' * (ARGUMENT_CHARACTER_LIMIT - len(raw)))
    executor.execute(invocation)
    with pytest.raises(ToolCallingError, match="invalid_arguments"):
        executor.execute(invocation.model_copy(update={"arguments": invocation.arguments + " "}))
    size = len(compact_json(executor.execute(call()).payload()))
    monkeypatch.setattr("evidenceops.tools.RESULT_CHARACTER_LIMIT", size)
    assert len(compact_json(executor.execute(call()).payload())) == size
    monkeypatch.setattr("evidenceops.tools.RESULT_CHARACTER_LIMIT", size - 1)
    with pytest.raises(ToolCallingError, match="result_too_large"):
        executor.execute(call())
    assert size < RESULT_CHARACTER_LIMIT


def test_oversized_detail_is_not_silently_truncated(backends):
    backends[1].return_value = document(abstract="x" * RESULT_CHARACTER_LIMIT)
    with pytest.raises(ToolCallingError, match="result_too_large"):
        ToolExecutor(*backends).execute(call("get_publication", {"publication_id": str(PUBLICATION_ID)}))


@pytest.mark.parametrize("elapsed,passes", [(TOOL_BUDGET_SECONDS, True), (TOOL_BUDGET_SECONDS + .01, False)])
def test_cooperative_budget_is_checked_after_backend_returns(backends, elapsed, passes):
    clock = Mock(side_effect=[100, 100 + elapsed])
    executor = ToolExecutor(*backends, clock=clock)
    if passes:
        executor.execute(call())
    else:
        with pytest.raises(ToolCallingError, match="tool_budget_exceeded"):
            executor.execute(call())
    backends[0].assert_called_once()  # Work ran; this is not hard cancellation.


@pytest.mark.parametrize("error,code", [
    (TimeoutError("sensitive backend"), "tool_timeout"),
    (RuntimeError("sensitive backend"), "backend_error"),
])
def test_backend_errors_are_safe_and_not_retried(backends, error, code):
    backends[0].side_effect = error
    with pytest.raises(ToolCallingError) as caught:
        ToolExecutor(*backends).execute(call())
    assert caught.value.code == code and "sensitive" not in str(caught.value)
    backends[0].assert_called_once()


def test_sql_cancellation_has_its_own_cause(backends):
    class Cancelled(Exception):
        sqlstate = "57014"
    backends[0].side_effect = DBAPIError("private SQL", {}, Cancelled("private"))
    with pytest.raises(ToolCallingError, match="sql_timeout"):
        ToolExecutor(*backends).execute(call())

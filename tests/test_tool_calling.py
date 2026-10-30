"""Bounded flow, source membership and content-safe logs/spans."""

import json
import logging
from unittest.mock import Mock

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause
from evidenceops.observability import JsonFormatter
from evidenceops.rag import ABSTENTION_ANSWER
from evidenceops.rag_errors import InvalidCitationsError
from evidenceops.tool_calling import ToolCallingService, ToolProposal
from evidenceops.tools import ToolCallingError, ToolExecutor
from evidenceops.tracing import provider
from test_tools import PUBLICATION_ID, backends, call


def model_for(invocation=None, answer="Publicación candidata [S1].", limitations=None):
    model = Mock()
    model.propose.return_value = ToolProposal(call() if invocation is None else invocation)
    model.finalize.return_value = GeneratedContent(answer=answer, limitations=limitations or [])
    return model


@pytest.mark.parametrize("name", ["search_evidence", "get_publication"])
def test_single_tool_round_reaches_final_answer_with_correlated_result(backends, name):
    invocation = call() if name == "search_evidence" else call(name, {"publication_id": str(PUBLICATION_ID)})
    model = model_for(invocation)
    response = ToolCallingService(model, ToolExecutor(*backends)).run(" private-question ")
    model.propose.assert_called_once()
    assert model.propose.call_args.args[0] == "private-question"
    model.finalize.assert_called_once_with("private-question", model.propose.return_value, response.tool_result)
    assert response.tool_result.call_id == invocation.id
    assert response.sources == response.tool_result.sources()
    assert len(response.sources) == 1 and response.operation_id
    assert response.sources[0].publication_id == PUBLICATION_ID
    if name == "search_evidence":
        assert "Solo se consultó metadata" in response.limitations[-1]


@pytest.mark.parametrize("name", ["search_evidence", "get_publication"])
def test_no_sources_only_allows_abstention(backends, name):
    backends[0].return_value = []
    backends[1].return_value = None
    invocation = call() if name == "search_evidence" else call(name, {"publication_id": str(PUBLICATION_ID)})
    model = model_for(invocation, answer=ABSTENTION_ANSWER)
    response = ToolCallingService(model, ToolExecutor(*backends)).run("question")
    assert response.answer == ABSTENTION_ANSWER and response.sources == ()
    assert response.limitations
    assert model.finalize.call_args.args[2].status == ("ok" if name == "search_evidence" else "error")
    model.finalize.return_value = GeneratedContent(answer="Invented evidence [S1].", limitations=[])
    with pytest.raises(InvalidCitationsError):
        ToolCallingService(model, ToolExecutor(*backends)).run("question")


def test_direct_answer_without_tools_requires_abstention(backends):
    model = model_for()
    model.propose.return_value = GeneratedContent(answer=ABSTENTION_ANSWER, limitations=[])
    response = ToolCallingService(model, ToolExecutor(*backends)).run("question")
    assert response.tool_result is None and response.sources == ()
    model.finalize.assert_not_called()
    assert not any(backend.called for backend in backends)
    model.propose.return_value = GeneratedContent(answer="Una respuesta sin fuentes", limitations=[])
    with pytest.raises(InvalidCitationsError):
        ToolCallingService(model, ToolExecutor(*backends)).run("question")


@pytest.mark.parametrize("invocation,code", [(call("unknown_tool"), "unknown_tool"),
    (call(arguments={"query": "x", "top_k": 10}), "invalid_arguments")])
def test_invalid_proposal_never_runs_backend_or_finalization(backends, invocation, code):
    model = model_for(invocation)
    with pytest.raises(ToolCallingError, match=code):
        ToolCallingService(model, ToolExecutor(*backends)).run("question")
    assert not any(backend.called for backend in backends)
    model.finalize.assert_not_called()


def test_second_round_is_never_executed_even_with_a_fake_model(backends):
    model = model_for()
    model.finalize.return_value = ToolProposal(call("get_publication", {"publication_id": str(PUBLICATION_ID)}))
    with pytest.raises(ToolCallingError, match="round_limit_exceeded"):
        ToolCallingService(model, ToolExecutor(*backends)).run("question")
    backends[0].assert_called_once()
    backends[1].assert_not_called()
    model.propose.assert_called_once()
    model.finalize.assert_called_once()


@pytest.mark.parametrize("answer,limitations,error", [
    ("Inventada [S2].", [], InvalidCitationsError),
    ("Sin citas", [], InvalidCitationsError),
    ("Con cita [S1].", ["Sin cita"], InvalidCitationsError),
    (ABSTENTION_ANSWER, ["Afirmación"], InvalidCitationsError),
    ("Referencia https://invented.example [S1].", [], ToolCallingError),
    ("DOI 10.1234/invented [S1].", [], ToolCallingError),
    ("PMID: 12345678 [S1].", [], ToolCallingError),
    ("PMID 12345678 [S1].", [], ToolCallingError),
])
def test_final_references_are_limited_to_returned_sources(backends, answer, limitations, error):
    model = model_for(answer=answer, limitations=limitations)
    with pytest.raises(error):
        ToolCallingService(model, ToolExecutor(*backends)).run("question")
    model.finalize.assert_called_once()  # No repair retries.


@pytest.mark.parametrize("stage", ["propose", "finalize"])
def test_provider_error_terminates_without_retry(backends, stage):
    model = model_for()
    getattr(model, stage).side_effect = GenerationError(GenerationErrorCause.TIMEOUT, "Safe timeout")
    with pytest.raises(GenerationError) as caught:
        ToolCallingService(model, ToolExecutor(*backends)).run("question")
    assert caught.value.cause is GenerationErrorCause.TIMEOUT
    assert getattr(model, stage).call_count == 1
    assert backends[0].call_count == (0 if stage == "propose" else 1)


def test_backend_failure_stops_before_finalization(backends):
    backends[0].side_effect = RuntimeError("sensitive-backend")
    model = model_for()
    with pytest.raises(ToolCallingError, match="backend_error"):
        ToolCallingService(model, ToolExecutor(*backends)).run("question")
    model.finalize.assert_not_called()


@pytest.fixture(scope="module")
def exporter():
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


@pytest.mark.parametrize("failed", [False, True])
def test_logs_and_spans_follow_one_success_or_failure_without_content(backends, caplog, exporter, failed):
    exporter.clear()
    model = model_for()
    if failed:
        backends[0].side_effect = RuntimeError("sensitive-backend")
    with caplog.at_level(logging.INFO, logger="evidenceops.tool_calling"):
        service = ToolCallingService(model, ToolExecutor(*backends))
        if failed:
            with pytest.raises(ToolCallingError):
                service.run("private-question")
        else:
            service.run("private-question")
    records = [json.loads(JsonFormatter().format(r)) for r in caplog.records if r.name == "evidenceops.tool_calling"]
    finished = [r for r in records if r["event"] == "tool_calling.finished"]
    assert len({r["operation_id"] for r in records}) == 1
    assert all(r["duration_ms"] >= 0 for r in finished)
    calls = [r for r in finished if r.get("call_id")]
    assert {r["call_id"] for r in calls} == {"call_1"}
    assert {r["tool"] for r in calls} == {"search_evidence"}
    spans = exporter.get_finished_spans()
    assert len({s.context.trace_id for s in spans}) == 1
    root = next(s for s in spans if s.name == "tool_calling.operation")
    assert all(s.parent.span_id == root.context.span_id for s in spans if s is not root)
    if failed:
        assert any(r["cause"] == "backend_error" for r in finished)
        assert root.attributes["evidenceops.error_cause"] == "backend_error"
    serialized = json.dumps(records) + json.dumps([{"attributes": dict(s.attributes),
        "events": [dict(e.attributes) for e in s.events]} for s in spans])
    for private in ("private-question", "sensitive-backend", "complete abstract", "Publicación candidata"):
        assert private not in serialized

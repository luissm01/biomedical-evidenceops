"""Deterministic graph routing, application budgets, citations and safe telemetry."""

import json
import logging
from dataclasses import replace
from unittest.mock import Mock
from uuid import UUID

import httpx
import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from evidenceops.agent import AgentService, HISTORY_CHARACTER_LIMIT
from evidenceops.agent_demo import SCENARIOS, run_demo
from evidenceops.deepseek_tools import DeepSeekToolCaller
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause
from evidenceops.observability import JsonFormatter
from evidenceops.rag import ABSTENTION_ANSWER
from evidenceops.tool_calling import ToolProposal
from evidenceops.tools import ToolExecutor, compact_json
from evidenceops.tracing import provider
from test_tools import PUBLICATION_ID, backends, call


def proposal(name="search_evidence", arguments=None, identifier="call_1"):
    return ToolProposal(call(name, arguments).model_copy(update={"id": identifier}))


def answer(text="Publicación candidata [S1]."):
    return GeneratedContent(answer=text, limitations=[])


def scripted(*turns):
    return Mock(decide=Mock(side_effect=list(turns)))


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_offline_demo_uses_real_graph_adapter_and_executor(scenario):
    result = run_demo(scenario)
    expected = {
        "evidence": ("answered", "final_answer"), "budget": ("answered", "final_answer"),
        "empty": ("abstained", "insufficient_evidence"), "not-found": ("abstained", "insufficient_evidence"),
        "no-abstract": ("abstained", "insufficient_evidence"), "repeat": ("limit_exceeded", "repeated_call"),
        "exhausted": ("limit_exceeded", "tool_call_limit"), "backend-error": ("error", "backend_error"),
        "model-error": ("error", "provider_unavailable"), "timeout": ("error", "timeout"),
        "invalid-citations": ("error", "invalid_citations"),
    }
    assert (result["status"], result["termination_reason"]) == expected[scenario]
    assert result["simulated_requests"] == result["llm_calls"] <= 4
    assert result["tool_calls"] <= 3 and result["steps"] <= 8
    assert (result["content"] is not None) == (result["status"] in {"answered", "abstained"})
    if scenario == "evidence":
        assert result["sources"][0]["detail_level"] == "abstract"
        assert (result["llm_calls"], result["tool_calls"], result["steps"]) == (3, 2, 6)
    if scenario in {"budget", "exhausted"}:
        assert (result["llm_calls"], result["tool_calls"], result["steps"]) == (4, 3, 8)


def test_sources_remain_stable_when_reading_second_search_hit(backends):
    retrieve, lookup = backends
    unit = retrieve.return_value[0].unit
    second_id = UUID("223e4567-e89b-42d3-a456-426614174000")
    second = type(retrieve.return_value[0])(replace(unit, publication_id=second_id, source_id="2"), .4)
    retrieve.return_value.append(second)
    lookup.return_value = replace(lookup.return_value, source_id="2")
    model = scripted(proposal(), proposal("get_publication", {"publication_id": str(second_id)}, "call_2"),
                     answer("Abstract leído [S2]."))
    result = AgentService(model, ToolExecutor(*backends)).run("question")
    assert result.status == "answered"
    assert [(s.citation_id, s.publication_id) for s in result.sources] == [("S1", PUBLICATION_ID), ("S2", second_id)]
    assert result.sources[1].abstract == lookup.return_value.abstract
    history = model.decide.call_args.args[0]
    assert json.loads(history[-1]["content"])["data"]["citation_id"] == "S2"
    assert history[-1]["tool_call_id"] == "call_2"
    assert len(history) == 6  # one history, no redundant evidence messages


def test_discovery_does_not_downgrade_previously_read_abstract(backends):
    model = scripted(proposal("get_publication", {"publication_id": str(PUBLICATION_ID)}),
                     proposal(identifier="call_2"), answer())
    result = AgentService(model, ToolExecutor(*backends)).run("question")
    assert result.status == "answered"
    assert result.sources[0].detail_level == "abstract"
    assert result.sources[0].citation_id == "S1"


def test_provenance_conflict_is_a_backend_error(backends):
    backends[1].return_value = replace(backends[1].return_value, source_id="different")
    model = scripted(proposal(), proposal("get_publication", {"publication_id": str(PUBLICATION_ID)}, "call_2"), answer())
    result = AgentService(model, ToolExecutor(*backends)).run("question")
    assert (result.status, result.termination_reason, result.content) == ("error", "backend_error", None)
    assert model.decide.call_count == 2


def test_missing_publication_is_a_recoverable_domain_result(backends):
    backends[1].return_value = None
    model = scripted(proposal("get_publication", {"publication_id": str(PUBLICATION_ID)}),
                     proposal(identifier="call_2"), answer())
    result = AgentService(model, ToolExecutor(*backends)).run("question")
    assert result.status == "answered" and result.tool_calls == 2
    history = model.decide.call_args_list[1].args[0]
    assert json.loads(history[-1]["content"])["error"]["code"] == "publication_not_found"


@pytest.mark.parametrize("text,expected", [(ABSTENTION_ANSWER, "abstained"), ("Invented [S1].", "error")])
def test_without_sources_only_abstention_is_accepted(backends, text, expected):
    model = scripted(answer(text))
    response = AgentService(model, ToolExecutor(*backends)).run("question")
    assert response.status == expected and response.sources == ()
    assert response.steps == 2 and response.llm_calls == 1 and response.tool_calls == 0
    assert not any(backend.called for backend in backends)


@pytest.mark.parametrize("text", ["Without citation", "Unknown [S99].", "DOI 10.1234/x [S1]."])
def test_invalid_answers_discard_candidate_without_repair(backends, text):
    model = scripted(proposal(), answer(text))
    response = AgentService(model, ToolExecutor(*backends)).run("question")
    assert response.status == "error" and response.content is None and response.llm_calls == 2


def test_canonical_repetition_ignores_call_id_json_order_defaults_and_outer_spaces(backends):
    model = scripted(proposal(arguments={"query": " x ", "top_k": 5}),
                     proposal(arguments={"query": "x"}, identifier="new_id"), answer())
    response = AgentService(model, ToolExecutor(*backends)).run("question")
    assert response.termination_reason == "repeated_call" and response.content is None
    assert response.tool_calls == 1 and model.decide.call_count == 2
    backends[0].assert_called_once()


def test_duplicate_native_call_id_is_rejected(backends):
    model = scripted(proposal(arguments={"query": "x"}), proposal(arguments={"query": "y"}))
    response = AgentService(model, ToolExecutor(*backends)).run("question")
    assert response.termination_reason == "invalid_call" and response.tool_calls == 1


@pytest.mark.parametrize("final", [answer(), answer(ABSTENTION_ANSWER), proposal(identifier="fourth")])
def test_maximum_path_reserves_fourth_llm_call_and_never_executes_fourth_tool(backends, final):
    model = scripted(*(proposal(arguments={"query": str(i)}, identifier=f"call_{i}") for i in range(3)), final)
    result = AgentService(model, ToolExecutor(*backends)).run("question")
    assert (result.llm_calls, result.tool_calls, result.steps) == (4, 3, 8)
    assert backends[0].call_count == 3
    assert model.decide.call_args.args[1] is None
    assert all(c.args[1] is not None for c in model.decide.call_args_list[:3])
    assert result.status == ("limit_exceeded" if isinstance(final, ToolProposal) else
                             "abstained" if final.answer == ABSTENTION_ANSWER else "answered")


@pytest.mark.parametrize("recursion_limit", [1, 2, 3, 7, 8, 9, 10])
def test_framework_recursion_limit_and_own_budgets_on_extreme_path(backends, recursion_limit):
    model = scripted(*(proposal(arguments={"query": str(i)}, identifier=f"call_{i}") for i in range(3)), answer())
    response = AgentService(model, ToolExecutor(*backends), recursion_limit=recursion_limit).run("question")
    assert response.steps <= min(recursion_limit, 8)
    assert response.llm_calls <= 4 and response.tool_calls <= 3
    if recursion_limit <= 8:
        assert response.termination_reason == "recursion_limit" and response.content is None
    else:
        assert response.status == "answered" and response.steps == 8


@pytest.mark.parametrize("stage", ["model", "tool", "final"])
@pytest.mark.parametrize("elapsed", [119.999, 120.0, 121.0])
def test_cooperative_time_budget_checks_after_work_and_does_not_cancel(backends, stage, elapsed):
    clock = Clock()
    def advance(value):
        def action(*args, **kwargs):
            clock.now = elapsed
            return value
        return action
    model = scripted(proposal(), answer())
    if stage == "model":
        model.decide.side_effect = advance(proposal())
    elif stage == "tool":
        backends[0].side_effect = advance(backends[0].return_value)
    else:
        model.decide.side_effect = [proposal(), None]
        def decide(*args, **kwargs):
            if len(args[0]) == 2:
                return proposal()
            return advance(answer())()
        model.decide.side_effect = decide
    result = AgentService(model, ToolExecutor(*backends), clock=clock).run("question")
    if elapsed >= 120:
        assert (result.status, result.termination_reason, result.content) == ("limit_exceeded", "time_budget", None)
        assert model.decide.call_count == (2 if stage == "final" else 1)
    elif stage != "model":
        assert result.status == "answered"
    assert result.steps <= 8
    if stage == "tool":
        backends[0].assert_called_once()  # Work has returned; no hard cancellation claim.
        if elapsed < 120:
            assert model.decide.call_args.kwargs["timeout_seconds"] == pytest.approx(.001)


@pytest.mark.parametrize("stage", ["initial", "reserved"])
def test_model_failure_counts_attempt_and_never_leaks_candidate(backends, stage):
    error = GenerationError(GenerationErrorCause.TIMEOUT, "private error")
    turns = [error] if stage == "initial" else [
        *(proposal(arguments={"query": str(i)}, identifier=f"call_{i}") for i in range(3)), error]
    model = scripted(*turns)
    response = AgentService(model, ToolExecutor(*backends)).run("question")
    assert response.status == "error" and response.termination_reason == "timeout" and response.content is None
    assert response.llm_calls == (1 if stage == "initial" else 4)


@pytest.mark.parametrize("invocation,reason", [
    (proposal("unknown"), "unknown_tool"),
    (proposal(arguments={"query": "x", "top_k": 99}), "invalid_arguments"),
])
def test_invalid_proposals_do_not_reach_backend(backends, invocation, reason):
    model = scripted(invocation)
    response = AgentService(model, ToolExecutor(*backends)).run("question")
    assert response.termination_reason == reason and response.tool_calls == 0
    assert not any(backend.called for backend in backends)


def test_backend_error_counts_attempt_and_stops_without_finalization(backends):
    backends[0].side_effect = RuntimeError("private backend")
    model = scripted(proposal(), answer())
    response = AgentService(model, ToolExecutor(*backends)).run("question")
    assert response.termination_reason == "backend_error" and response.content is None
    assert response.tool_calls == 1 and response.llm_calls == 1


def test_history_exact_boundary_and_overflow_before_provider(backends, monkeypatch):
    model = scripted(answer(ABSTENTION_ANSWER))
    service = AgentService(model, ToolExecutor(*backends))
    service.run("question")
    size = len(compact_json(model.decide.call_args.args[0]))
    assert size < HISTORY_CHARACTER_LIMIT
    monkeypatch.setattr("evidenceops.agent.HISTORY_CHARACTER_LIMIT", size)
    assert AgentService(scripted(answer(ABSTENTION_ANSWER)), ToolExecutor(*backends)).run("question").status == "abstained"
    monkeypatch.setattr("evidenceops.agent.HISTORY_CHARACTER_LIMIT", size - 1)
    rejected_model = scripted(answer())
    result = AgentService(rejected_model, ToolExecutor(*backends)).run("question")
    assert result.termination_reason == "history_limit" and result.llm_calls == 0
    rejected_model.decide.assert_not_called()


def test_history_overflow_after_tool_is_not_truncated_or_sent(backends, monkeypatch):
    model = scripted(proposal(), answer())
    monkeypatch.setattr("evidenceops.agent.HISTORY_CHARACTER_LIMIT", 3000)
    backends[1].return_value = replace(backends[1].return_value, abstract="x" * 4000)
    model.decide.side_effect = [proposal("get_publication", {"publication_id": str(PUBLICATION_ID)}), answer()]
    response = AgentService(model, ToolExecutor(*backends)).run("question")
    assert response.termination_reason == "history_limit" and response.content is None
    assert response.sources == () and model.decide.call_count == 1 and response.tool_calls == 1


def test_operation_state_is_not_shared_across_runs(backends):
    model = scripted(proposal(), answer(), answer(ABSTENTION_ANSWER))
    service = AgentService(model, ToolExecutor(*backends))
    first, second = service.run("first"), service.run("second")
    assert first.operation_id != second.operation_id
    assert second.sources == () and second.tool_calls == 0 and second.llm_calls == 1
    assert len(model.decide.call_args.args[0]) == 2


def test_input_is_validated_before_model_or_backend(backends):
    model = scripted(answer())
    with pytest.raises(ValueError):
        AgentService(model, ToolExecutor(*backends)).run(" ")
    model.decide.assert_not_called()


def test_http_timeout_is_capped_without_changing_client_default():
    requests = []
    def transport(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"answer": ABSTENTION_ANSWER, "limitations": []})}}]})
    model = DeepSeekToolCaller("fake", timeout_seconds=60, transport=httpx.MockTransport(transport))
    try:
        model.decide([], None, timeout_seconds=.125)
        model.decide([], None, timeout_seconds=90)
        assert set(requests[0].extensions["timeout"].values()) == {.125}
        assert set(requests[1].extensions["timeout"].values()) == {60}
    finally:
        model.close()


@pytest.mark.parametrize("failed", [False, True])
def test_logs_and_spans_show_routing_counters_and_safe_causes(backends, caplog, failed):
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    model = scripted(proposal(), answer())
    if failed:
        backends[0].side_effect = RuntimeError("private-backend")
    with caplog.at_level(logging.INFO, logger="evidenceops.agent"):
        result = AgentService(model, ToolExecutor(*backends)).run("private-question")
    records = [json.loads(JsonFormatter().format(r)) for r in caplog.records if r.name == "evidenceops.agent"]
    assert len(records) == result.steps + 1
    assert {r["operation_id"] for r in records} == {result.operation_id}
    assert records[0]["transition"] == "execute"
    execution = next(r for r in records if r["stage"] == "execute")
    assert execution["call_id"] == "call_1" and execution["tool"] == "search_evidence"
    assert records[-1]["llm_calls"] == result.llm_calls
    assert records[-1]["cause"] == result.termination_reason
    spans = exporter.get_finished_spans()
    assert len({s.context.trace_id for s in spans}) == 1
    root = next(s for s in spans if s.name == "agent.operation")
    assert all(s.parent.span_id == root.context.span_id for s in spans if s is not root)
    serialized = json.dumps(records) + json.dumps([dict(s.attributes) for s in spans])
    for private in ("private-question", "private-backend", "complete abstract", "Publicación candidata"):
        assert private not in serialized

"""Actual HTTP serialization and two-turn protocol over an in-memory transport."""

import json
from contextlib import closing
from unittest.mock import Mock

import httpx
import pytest

from evidenceops.config import GenerationSettings
from evidenceops.deepseek_tools import DeepSeekToolCaller, create_deepseek_tool_caller
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause
from evidenceops.metrics import GenerationMetrics
from evidenceops.rag import ABSTENTION_ANSWER
from evidenceops.tool_calling import ToolCallingService, ToolProposal
from evidenceops.tools import TOOL_DEFINITIONS, ToolCallingError, ToolExecutor
from test_tools import PUBLICATION_ID, backends, call


def tool_response(invocation=None):
    invocation = call() if invocation is None else invocation
    return {"choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None, "tool_calls": [{"id": invocation.id,
        "type": "function", "function": {"name": invocation.name, "arguments": invocation.arguments}}]}}]}


def final_response(answer="Publicaciones candidatas [S1]."):
    return {"choices": [{"finish_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps({"answer": answer, "limitations": []})}}]}


@pytest.mark.parametrize("name", ["search_evidence", "get_publication"])
def test_entire_flow_over_transport_preserves_native_call_and_no_thinking(backends, name):
    requests = []
    invocation = call() if name == "search_evidence" else call(name, {"publication_id": str(PUBLICATION_ID)})
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=tool_response(invocation) if len(requests) == 1 else final_response())
    with closing(DeepSeekToolCaller("fake-only", transport=httpx.MockTransport(respond))) as model:
        response = ToolCallingService(model, ToolExecutor(*backends)).run("question")
    assert len(requests) == 2
    first, second = (json.loads(r.content) for r in requests)
    assert all(r.url == "https://api.deepseek.com/chat/completions" for r in requests)
    assert all(r.headers["authorization"] == "Bearer fake-only" for r in requests)
    assert first["model"] == second["model"] == "deepseek-flash"
    assert first["thinking"] == second["thinking"] == {"type": "disabled"}
    assert not first["stream"] and not second["stream"]
    assert first["max_tokens"] == second["max_tokens"] == 2048
    assert {t["function"]["name"] for t in first["tools"]} == {"search_evidence", "get_publication"}
    assert first["tool_choice"] == "auto" and "response_format" not in first
    assert second["tool_choice"] == "none" and "tools" not in second
    assert second["response_format"] == {"type": "json_object"}
    assert second["messages"][:2] == first["messages"]
    assert second["messages"][2] == tool_response(invocation)["choices"][0]["message"]
    assert second["messages"][3]["role"] == "tool"
    assert second["messages"][3]["tool_call_id"] == invocation.id
    assert json.loads(second["messages"][3]["content"]) == response.tool_result.payload()


def test_many_calls_are_rejected_before_execution(backends):
    payload = tool_response()
    payload["choices"][0]["message"]["tool_calls"] *= 2
    handler = Mock(return_value=httpx.Response(200, json=payload))
    with closing(DeepSeekToolCaller("fake-only", transport=httpx.MockTransport(handler))) as model:
        with pytest.raises(ToolCallingError, match="call_limit_exceeded"):
            ToolCallingService(model, ToolExecutor(*backends)).run("question")
    handler.assert_called_once()
    assert not any(backend.called for backend in backends)


def test_new_round_from_provider_is_rejected_without_third_request(backends):
    handler = Mock(side_effect=[httpx.Response(200, json=tool_response()),
                               httpx.Response(200, json=tool_response())])
    with closing(DeepSeekToolCaller("fake-only", transport=httpx.MockTransport(handler))) as model:
        with pytest.raises(ToolCallingError, match="round_limit_exceeded"):
            ToolCallingService(model, ToolExecutor(*backends)).run("question")
    assert handler.call_count == 2
    backends[0].assert_called_once()
    backends[1].assert_not_called()


@pytest.mark.parametrize("status,cause", [
    (408, "timeout"), (429, "rate_limit"), (401, "authentication"),
    (403, "authentication"), (402, "provider_unavailable"),
    (503, "provider_unavailable"), (400, "unknown"),
])
def test_safe_http_errors_and_zero_retries(backends, status, cause):
    handler = Mock(return_value=httpx.Response(status, json={"private": "private-provider-body"}))
    with closing(DeepSeekToolCaller("fake-only", transport=httpx.MockTransport(handler))) as model:
        with pytest.raises(GenerationError) as caught:
            ToolCallingService(model, ToolExecutor(*backends)).run("question")
    assert caught.value.cause.value == cause
    assert "private" not in str(caught.value)
    handler.assert_called_once()
    assert not any(backend.called for backend in backends)


def test_effective_transport_timeout_configuration_and_classification():
    handler = Mock(side_effect=httpx.ReadTimeout("private-provider-body"))
    with closing(DeepSeekToolCaller("fake-only", timeout_seconds=0.2,
                                   transport=httpx.MockTransport(handler))) as model:
        with pytest.raises(GenerationError) as caught:
            model.propose("question", TOOL_DEFINITIONS)
    assert caught.value.cause is GenerationErrorCause.TIMEOUT
    assert handler.call_args.args[0].extensions["timeout"] == {
        "connect": .2, "read": .2, "write": .2, "pool": .2}
    handler.assert_called_once()


@pytest.mark.parametrize("payload", [
    {}, {"choices": []}, {"choices": [None]}, [],
    {"choices": [{"finish_reason": "length", "message": {"content": "private-partial"}}]},
    {"choices": [{"finish_reason": "stop", "message": {"content": "not-json"}}]},
    {"choices": [{"finish_reason": "stop", "message": {"content": '{"answer":"","limitations":[]}'}}]},
    {"choices": [{"finish_reason": "tool_calls", "message": {"tool_calls": []}}]},
    {"choices": [{"finish_reason": "tool_calls", "message": {"tool_calls": "invalid"}}]},
    {"choices": [{"finish_reason": "tool_calls", "message": {"tool_calls": [{"type": "not-function"}]}}]},
])
def test_malformed_provider_outputs_are_safe_invalid_output(payload):
    handler = Mock(return_value=httpx.Response(200, json=payload))
    with closing(DeepSeekToolCaller("fake-only", transport=httpx.MockTransport(handler))) as model:
        with pytest.raises(GenerationError) as caught:
            model.propose("question", TOOL_DEFINITIONS)
    assert caught.value.cause is GenerationErrorCause.INVALID_OUTPUT
    assert "private" not in str(caught.value)
    handler.assert_called_once()


def test_mismatched_result_id_is_never_sent(backends):
    result = ToolExecutor(*backends).execute(call())
    handler = Mock()
    with closing(DeepSeekToolCaller("fake-only", transport=httpx.MockTransport(handler))) as model:
        with pytest.raises(ToolCallingError, match="invalid_call"):
            model.finalize("question", ToolProposal(call()), result.model_copy(update={"call_id": "wrong"}))
    handler.assert_not_called()


def test_direct_abstention_and_usage_are_observed(backends):
    metrics = GenerationMetrics()
    payload = final_response(ABSTENTION_ANSWER)
    payload["usage"] = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    handler = Mock(return_value=httpx.Response(200, json=payload))
    with closing(DeepSeekToolCaller("fake-only", transport=httpx.MockTransport(handler), metrics=metrics)) as model:
        response = ToolCallingService(model, ToolExecutor(*backends)).run("question")
    assert response.answer == ABSTENTION_ANSWER and response.sources == ()
    handler.assert_called_once()
    assert not any(backend.called for backend in backends)
    assert metrics.registry.get_sample_value("evidenceops_llm_total_tokens_total", {
        "provider": "deepseek", "model": "deepseek-flash"}) == 30


def test_factory_uses_only_deepseek_settings_without_changing_generator_selection(monkeypatch):
    constructor = Mock()
    monkeypatch.setattr("evidenceops.deepseek_tools.DeepSeekToolCaller", constructor)
    settings = GenerationSettings(_env_file=None, llm_provider="gemini", deepseek_api_key="fake-only")
    assert create_deepseek_tool_caller(settings) is constructor.return_value
    assert settings.llm_provider == "gemini"
    assert constructor.call_args.kwargs["model"] == "deepseek-flash"
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        create_deepseek_tool_caller(GenerationSettings(_env_file=None, deepseek_api_key=None))

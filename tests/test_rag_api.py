"""HTTP → real RAG orchestration → simulated boundaries; no model inference."""

from dataclasses import asdict
import io
import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from sqlalchemy.exc import OperationalError

from evidenceops.deepseek import DeepSeekGenerator
from evidenceops.embeddings import EmbeddingCompatibilityError
from evidenceops.gemini import GeminiGenerator
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause
from evidenceops.main import create_app, get_rag_service
from evidenceops.observability import JsonFormatter
from evidenceops.rag import ABSTENTION_ANSWER, RagService
from evidenceops.tracing import provider
from test_rag import result


@pytest.fixture(scope="module")
def exporter():
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


@pytest.fixture
def flow(exporter):
    exporter.clear()
    app = create_app()
    retrieve = Mock(return_value=[result(abstract="private-evidence")])
    generator = Mock()
    generator.generate.return_value = GeneratedContent(answer="private-answer [S1].", limitations=[])
    service = RagService(retrieve, generator, app.state.metrics)
    app.dependency_overrides[get_rag_service] = lambda: service
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("evidenceops")
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        yield SimpleNamespace(
            app=app, client=TestClient(app, raise_server_exceptions=False),
            retrieve=retrieve, generator=generator, exporter=exporter, stream=stream,
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def call(flow, **kwargs):
    return flow.client.post("/rag", json={"query": " private-query ", **kwargs})


def test_http_contract_and_complete_observability(flow):
    response = call(flow, published_from=2020)
    assert response.status_code == 200
    assert set(response.json()) == {"answer", "limitations", "sources"}
    assert response.json()["sources"] == json.loads(json.dumps([
        {"citation_id": "S1", "unit": asdict(flow.retrieve.return_value[0].unit), "score": 0.75},
    ], default=str))
    flow.retrieve.assert_called_once_with(query="private-query", top_k=5, published_from=2020)
    message = json.loads(flow.generator.generate.call_args.args[0])
    assert message["query"] == "private-query"
    assert message["evidence"][0]["text"].endswith("private-evidence")
    assert flow.generator.generate.call_args.kwargs["system_instruction"]

    spans = {s.name: s for s in flow.exporter.get_finished_spans()}
    assert set(spans) == {"POST /rag", "rag", "rag.retrieval", "rag.context", "rag.generation"}
    assert spans["rag"].parent.span_id == spans["POST /rag"].context.span_id
    for name in ("rag.retrieval", "rag.context", "rag.generation"):
        assert spans[name].parent.span_id == spans["rag"].context.span_id
    assert all(s.status.status_code == StatusCode.OK for s in spans.values())
    assert len({s.context.trace_id for s in spans.values()}) == 1
    events = [json.loads(line) for line in flow.stream.getvalue().splitlines()]
    assert len(events) == 8
    assert {e["request_id"] for e in events} == {response.headers["X-Request-ID"]}
    assert {e["trace_id"] for e in events} == {format(spans["rag"].context.trace_id, "032x")}
    registry = flow.app.state.metrics.registry
    for stage in ("operation", "retrieval", "context", "generation"):
        labels = {"stage": stage, "outcome": "success"}
        assert registry.get_sample_value("evidenceops_rag_operations_total", labels) == 1
        assert registry.get_sample_value("evidenceops_rag_duration_seconds_count", labels) == 1
        assert registry.get_sample_value("evidenceops_rag_duration_seconds_sum", labels) >= 0
    exported = flow.client.get("/metrics").text + flow.stream.getvalue()
    exported += json.dumps([s.to_json() for s in spans.values()])
    assert "private-" not in exported
    assert 'request_id=' not in flow.client.get("/metrics").text


@pytest.mark.parametrize("kind", ["empty", "oversized", "model"])
def test_abstention_is_200_with_expected_stages(flow, kind):
    if kind == "empty":
        flow.retrieve.return_value = []
    elif kind == "oversized":
        flow.retrieve.return_value = [result(abstract="x" * 20_000)]
    else:
        flow.generator.generate.return_value = GeneratedContent(answer=ABSTENTION_ANSWER, limitations=[])
    response = call(flow)
    assert response.status_code == 200
    assert response.json()["answer"] == ABSTENTION_ANSWER
    assert bool(response.json()["sources"]) == (kind == "model")
    assert response.json()["limitations"]
    assert flow.generator.generate.call_count == (1 if kind == "model" else 0)
    spans = {s.name: s for s in flow.exporter.get_finished_spans()}
    assert ("rag.generation" in spans) == (kind == "model")
    assert spans["rag"].attributes["evidenceops.outcome"] == "abstention"
    assert spans["rag"].status.status_code == StatusCode.OK
    assert flow.app.state.metrics.registry.get_sample_value(
        "evidenceops_rag_operations_total", {"stage": "operation", "outcome": "abstention"},
    ) == 1


@pytest.mark.parametrize("body", [
    {}, {"query": " "}, {"query": "x" * 2001}, {"query": 5},
    {"query": "x", "published_from": 0}, {"query": "x", "published_from": True},
    {"query": "x", "published_from": "2020"}, {"query": "x", "published_from": 2020.5},
    {"query": "x", "top_k": 10},
])
def test_invalid_requests_do_not_run_rag(flow, body):
    response = flow.client.post("/rag", json=body)
    assert response.status_code == 422
    assert response.headers["X-Request-ID"]
    flow.retrieve.assert_not_called()
    flow.generator.generate.assert_not_called()
    assert [s.name for s in flow.exporter.get_finished_spans()] == ["POST /rag"]


@pytest.mark.parametrize("error,status,code", [
    (GenerationErrorCause.TIMEOUT, 504, "generation_timeout"),
    (GenerationErrorCause.RATE_LIMIT, 429, "generation_rate_limited"),
    (GenerationErrorCause.AUTHENTICATION, 503, "generation_unavailable"),
    (GenerationErrorCause.PROVIDER_UNAVAILABLE, 503, "generation_unavailable"),
    (GenerationErrorCause.INVALID_OUTPUT, 502, "invalid_generation"),
    (GenerationErrorCause.UNKNOWN, 502, "generation_failed"),
    ("citations", 502, "invalid_citations"),
    ("db", 503, "database_unavailable"),
    ("incompatible", 503, "retrieval_incompatible"),
    ("encoder", 503, "retrieval_unavailable"),
    ("unexpected", 500, None),
    ("context", 500, None),
])
def test_errors_and_safe_observability(flow, monkeypatch, error, status, code):
    stage = "generation"
    cause = error.value if isinstance(error, GenerationErrorCause) else code
    if isinstance(error, GenerationErrorCause):
        flow.generator.generate.side_effect = GenerationError(error, "private-provider-body private-key")
    elif error == "citations":
        flow.generator.generate.return_value = GeneratedContent(answer="private-answer [S99].", limitations=[])
    elif error in ("db", "incompatible", "encoder", "unexpected"):
        stage = "retrieval"
        flow.retrieve.side_effect = {
            "db": OperationalError("private-query", {}, Exception("private-db")),
            "incompatible": EmbeddingCompatibilityError("private-configuration"),
            "encoder": RuntimeError("private-model"),
            "unexpected": TypeError("private-bug"),
        }[error]
    else:
        stage = "context"
        monkeypatch.setattr("evidenceops.rag.build_context", Mock(side_effect=TypeError("private-bug")))
    if error in ("unexpected", "context"):
        cause = "unexpected_application_error"
    response = call(flow)
    assert response.status_code == status
    assert response.headers["X-Request-ID"]
    if code:
        assert response.json()["detail"]["code"] == code
    if stage != "generation":
        flow.generator.generate.assert_not_called()
    else:
        flow.generator.generate.assert_called_once()
    spans = {s.name: s for s in flow.exporter.get_finished_spans()}
    for name in ("POST /rag", "rag", f"rag.{stage}"):
        assert spans[name].status.status_code == StatusCode.ERROR
    for name in ("rag", f"rag.{stage}"):
        assert spans[name].attributes["evidenceops.error_cause"] == cause
    for stage_name in ("operation", stage):
        assert flow.app.state.metrics.registry.get_sample_value(
            "evidenceops_rag_errors_total", {"stage": stage_name, "cause": cause},
        ) == 1
    assert "private-" not in (response.text + flow.stream.getvalue() + json.dumps([
        s.to_json() for s in spans.values()
    ]))


@pytest.mark.parametrize("provider_name", ["gemini", "deepseek"])
def test_real_adapters_over_simulated_transport(flow, monkeypatch, provider_name):
    output = '{"answer":"private-answer [S1].","limitations":[]}'
    if provider_name == "gemini":
        sdk = SimpleNamespace(interactions=SimpleNamespace(create=Mock(return_value=SimpleNamespace(
            output_text=output,
        ))), close=Mock())
        monkeypatch.setattr("evidenceops.gemini.genai.Client", Mock(return_value=sdk))
        generator = GeminiGenerator(api_key="private-key", model="test-model")
    else:
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {"content": output}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }))
        client = httpx.Client(transport=transport)
        monkeypatch.setattr("evidenceops.deepseek.httpx.Client", lambda **kwargs: client)
        generator = DeepSeekGenerator(api_key="private-key", model="test-model", metrics=flow.app.state.metrics)
    flow.app.dependency_overrides[get_rag_service] = lambda: RagService(
        flow.retrieve, generator, flow.app.state.metrics,
    )
    try:
        response = call(flow)
    finally:
        generator.close()
    assert response.status_code == 200
    spans = {s.name: s for s in flow.exporter.get_finished_spans()}
    assert spans[f"llm.{provider_name}"].parent.span_id == spans["rag.generation"].context.span_id
    if provider_name == "deepseek":
        assert flow.app.state.metrics.registry.get_sample_value(
            "evidenceops_llm_total_tokens_total", {"provider": "deepseek", "model": "test-model"},
        ) == 15


@pytest.mark.parametrize("answer,limitations,reason,field", [
    ("private-answer [S99].", [], "unknown_citation", "answer"),
    ("private-answer [S01].", [], "malformed_citation", "answer"),
    ("private-answer.\n\nCitado [S1].", [], "block_missing_citation", "answer"),
    ("private-answer [S1] después.", [], "block_not_cited_at_end", "answer"),
    (ABSTENTION_ANSWER, ["private-limitation"], "invalid_abstention", "limitations"),
    ("private-answer [S1].", ["private-limitation"], "block_missing_citation", "limitations"),
])
def test_deepseek_success_then_citation_failure_has_safe_diagnostic(
    flow, monkeypatch, answer, limitations, reason, field,
):
    transport_calls = []

    def respond(request):
        transport_calls.append(request)
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps({"answer": answer, "limitations": limitations}),
            }}],
        })

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("evidenceops.deepseek.httpx.Client", lambda **kwargs: client)
    generator = DeepSeekGenerator(api_key="private-key", model="test-model")
    flow.app.dependency_overrides[get_rag_service] = lambda: RagService(
        flow.retrieve, generator, flow.app.state.metrics,
    )
    try:
        response = call(flow)
    finally:
        generator.close()
    assert len(transport_calls) == 1  # No retry or repair.
    assert response.status_code == 502
    assert response.json() == {"detail": {
        "code": "invalid_citations", "message": "Generation returned invalid citations",
    }}
    spans = {s.name: s for s in flow.exporter.get_finished_spans()}
    assert spans["llm.deepseek"].status.status_code == StatusCode.OK
    diagnostics = []
    for name in ("rag", "rag.generation"):
        assert spans[name].status.status_code == StatusCode.ERROR
        attrs = spans[name].attributes
        assert attrs["evidenceops.validation_reason"] == reason
        assert attrs["evidenceops.validation_field"] == field
        diagnostics.append({key.removeprefix("evidenceops."): value for key, value in attrs.items()
                            if key.startswith("evidenceops.") and key.removeprefix("evidenceops.") in {
                                "validation_reason", "validation_field", "limitation_index",
                                "block_index", "character_offset",
                            }})
    events = [json.loads(line) for line in flow.stream.getvalue().splitlines()]
    failures = [e for e in events if e.get("cause") == "invalid_citations"]
    assert {e["stage"] for e in failures} == {"operation", "generation"}
    for event, diagnostic in zip(failures, diagnostics):
        assert {key: event[key] for key in diagnostic} == diagnostic
        assert event["request_id"] == response.headers["X-Request-ID"]
        assert event["trace_id"] == format(spans["rag"].context.trace_id, "032x")
        assert ("limitation_index" in event) == (field == "limitations")
        assert ("block_index" in event) == (reason != "invalid_abstention")
    metrics = flow.client.get("/metrics").text
    assert "validation_reason" not in metrics and "character_offset" not in metrics
    assert "private-" not in (
        flow.stream.getvalue() + metrics + json.dumps([s.to_json() for s in spans.values()])
        + response.text
    )

"""Trace hierarchy and privacy using simulated provider responses."""

import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from evidenceops.deepseek import DeepSeekGenerator
from evidenceops.gemini import GeminiGenerator
from evidenceops.main import create_app, get_generator, get_question_text
from evidenceops.tracing import provider


@pytest.fixture(scope="module")
def exporter():
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


@pytest.mark.parametrize("case,expected_status,expected_cause", [
    ("success", 200, None),
    ("provider_error", 502, "unknown"),
    ("invalid_output", 502, "invalid_output"),
])
def test_gemini_trace_hierarchy_outcome_and_privacy(
    exporter, monkeypatch, case, expected_status, expected_cause
):
    exporter.clear()
    output = '{"answer":"private-answer","limitations":["private-limitation"]}'
    if case == "invalid_output":
        output = "private-invalid-output"
    create = Mock(return_value=SimpleNamespace(output_text=output))
    if case == "provider_error":
        create.side_effect = RuntimeError("private-provider-body private-key")
    sdk = SimpleNamespace(interactions=SimpleNamespace(create=create), close=Mock())
    monkeypatch.setattr("evidenceops.gemini.genai.Client", Mock(return_value=sdk))

    generator = GeminiGenerator(api_key="private-key", model="test-model")
    app = create_app()
    app.dependency_overrides[get_question_text] = lambda: "private-question"
    app.dependency_overrides[get_generator] = lambda: generator
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            f"/questions/{uuid4()}/generate"
        )
    finally:
        generator.close()

    assert response.status_code == expected_status
    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert set(spans) == {
        "POST /questions/{question_id}/generate", "generation", "llm.gemini"
    }
    http, generation, gemini = (spans[name] for name in (
        "POST /questions/{question_id}/generate", "generation", "llm.gemini"
    ))
    assert http.context.trace_id == generation.context.trace_id == gemini.context.trace_id
    assert generation.parent.span_id == http.context.span_id
    assert gemini.parent.span_id == generation.context.span_id
    assert http.kind.name == "SERVER"
    assert http.attributes["http.route"] == "/questions/{question_id}/generate"
    assert gemini.attributes["evidenceops.provider"] == "gemini"
    assert gemini.attributes["evidenceops.model"] == "test-model"
    assert all(span.end_time >= span.start_time for span in spans.values())

    expected_outcome = "error" if expected_cause else "success"
    for span in spans.values():
        assert span.attributes["evidenceops.outcome"] == expected_outcome
        assert span.status.status_code == (StatusCode.ERROR if expected_cause else StatusCode.OK)
    if expected_cause:
        assert gemini.attributes["evidenceops.error_cause"] == expected_cause
        assert generation.attributes["evidenceops.error_cause"] == expected_cause
        assert len(gemini.events) == len(generation.events) == 1
        assert gemini.events[0].name == "exception"
        assert gemini.events[0].attributes["exception.message"] == expected_cause
    else:
        assert not gemini.events

    exported = json.dumps([{
        "name": span.name,
        "attributes": dict(span.attributes),
        "events": [dict(event.attributes) for event in span.events],
    } for span in spans.values()])
    assert "private-" not in exported


def test_deepseek_adapter_has_provider_span(exporter, monkeypatch):
    exporter.clear()
    payload = {"choices": [{"finish_reason": "stop", "message": {
        "content": '{"answer":"private-answer","limitations":[]}'
    }}]}
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    ))
    monkeypatch.setattr("evidenceops.deepseek.httpx.Client", lambda **kwargs: client)
    generator = DeepSeekGenerator(api_key="private-key", model="test-deepseek")
    try:
        assert generator.generate("private-question").answer == "private-answer"
    finally:
        generator.close()
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "llm.deepseek"
    assert spans[0].attributes["evidenceops.provider"] == "deepseek"
    assert spans[0].attributes["evidenceops.model"] == "test-deepseek"
    assert spans[0].attributes["evidenceops.outcome"] == "success"

"""Generation metrics use isolated registries and simulated providers."""

import json
from contextlib import closing

import httpx
import pytest
from fastapi import HTTPException
from google import genai

from evidenceops.deepseek import DeepSeekGenerator
from evidenceops.gemini import GeminiGenerator
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause
from evidenceops.main import create_app, generate_answer, metrics_endpoint
from evidenceops.metrics import GenerationMetrics


def test_generation_metrics_aggregate_and_export():
    class Generator:
        calls = 0

        def generate(self, question_text):
            self.calls += 1
            if self.calls == 3:
                raise GenerationError(GenerationErrorCause.RATE_LIMIT, "private detail")
            if self.calls == 4:
                raise RuntimeError("private detail")
            return GeneratedContent(answer="answer", limitations=[])

    generator = Generator()
    app = create_app()
    metrics = app.state.metrics
    for _ in range(2):
        assert generate_answer("private question", generator, metrics).answer == "answer"
    with pytest.raises(HTTPException) as known_error:
        generate_answer("private question", generator, metrics)
    assert known_error.value.status_code == 429
    with pytest.raises(RuntimeError):
        generate_answer("private question", generator, metrics)

    registry = metrics.registry
    assert registry.get_sample_value("evidenceops_generations_total", {"outcome": "success"}) == 2
    assert registry.get_sample_value("evidenceops_generations_total", {"outcome": "error"}) == 2
    assert registry.get_sample_value("evidenceops_generation_errors_total", {"cause": "rate_limit"}) == 1
    assert registry.get_sample_value("evidenceops_generation_errors_total", {"cause": "unexpected_application_error"}) == 1
    assert registry.get_sample_value("evidenceops_generation_duration_seconds_count", {"outcome": "success"}) == 2
    assert registry.get_sample_value("evidenceops_generation_duration_seconds_count", {"outcome": "error"}) == 2
    response = metrics_endpoint(metrics)
    body = response.body.decode()
    assert "get" in app.openapi()["paths"]["/metrics"]
    assert "text/plain" in response.media_type
    assert 'evidenceops_generations_total{outcome="success"} 2.0' in body
    assert "evidenceops_generation_duration_seconds_bucket" in body
    assert 'request_id=' not in body
    assert 'question_id=' not in body
    assert 'provider=' not in body
    assert 'model=' not in body
    assert app.state.metrics.registry is not create_app().state.metrics.registry


@pytest.mark.parametrize("usage,expected", [
    ({"total_input_tokens": 3, "total_output_tokens": 5, "total_tokens": 9}, (3, 5, 9)),
    ({"total_input_tokens": 3}, None),
    (None, None),
])
def test_gemini_usage_from_interaction(monkeypatch, usage, expected):
    response = {
        "status": "completed",
        "steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps({"answer": "ok", "limitations": []})}]}],
    }
    if usage is not None:
        response["usage"] = usage
    client = genai.Client(api_key="test-key", http_options={"client_args": {"transport": httpx.MockTransport(lambda request: httpx.Response(200, json=response))}})
    monkeypatch.setattr("evidenceops.gemini.genai.Client", lambda **kwargs: client)
    metrics = GenerationMetrics()
    with closing(GeminiGenerator("test-key", model="test-gemini", metrics=metrics)) as generator:
        assert generator.generate("question").answer == "ok"
    labels = {"provider": "gemini", "model": "test-gemini"}
    for name, value in zip(("input", "output", "total"), expected or (None, None, None)):
        assert metrics.registry.get_sample_value(f"evidenceops_llm_{name}_tokens_total", labels) == value


@pytest.mark.parametrize("usage,expected", [
    ({"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10}, (4, 6, 10)),
    ({"prompt_tokens": 4}, None),
    (None, None),
])
def test_deepseek_usage_from_response(monkeypatch, usage, expected):
    response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"answer": "ok", "limitations": []})}}]}
    if usage is not None:
        response["usage"] = usage
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)))
    monkeypatch.setattr("evidenceops.deepseek.httpx.Client", lambda **kwargs: client)
    metrics = GenerationMetrics()
    with closing(DeepSeekGenerator("test-key", model="test-deepseek", metrics=metrics)) as generator:
        assert generator.generate("question").answer == "ok"
    labels = {"provider": "deepseek", "model": "test-deepseek"}
    for name, value in zip(("input", "output", "total"), expected or (None, None, None)):
        assert metrics.registry.get_sample_value(f"evidenceops_llm_{name}_tokens_total", labels) == value
    assert 'request_id=' not in metrics.render().decode()
    assert 'question_id=' not in metrics.render().decode()

import json
import logging
from contextlib import closing
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from evidenceops.config import GenerationSettings
from evidenceops.deepseek import DeepSeekGenerator
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause
from evidenceops.generator_factory import create_generator
from evidenceops.observability import JsonFormatter


@pytest.fixture
def transport(monkeypatch):
    handler = Mock(return_value=httpx.Response(200, json={
        "choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"answer": "Respuesta", "limitations": []})}}],
    }))
    client = httpx.Client(transport=httpx.MockTransport(handler))
    constructor = Mock(return_value=client)
    monkeypatch.setattr("evidenceops.deepseek.httpx.Client", constructor)
    return handler, constructor


def test_success_and_request(transport):
    with closing(DeepSeekGenerator("private-key", model="deepseek-flash")) as generator:
        result = generator.generate("private-question")
    assert result == GeneratedContent(answer="Respuesta", limitations=[])
    request = transport[0].call_args.args[0]
    body = json.loads(request.content)
    assert body["messages"][1]["content"] == "private-question"
    assert "biomédicas" in body["messages"][0]["content"]
    assert body["response_format"] == {"type": "json_object"}
    assert "JSON" in body["messages"][0]["content"]
    assert '{"answer": ' in body["messages"][0]["content"]
    assert '"limitations": [' in body["messages"][0]["content"]
    assert transport[1].call_args.kwargs["headers"]["Authorization"] == "Bearer private-key"
    assert transport[1].call_args.kwargs["timeout"] == 60.0


@pytest.mark.parametrize("payload", [
    {"choices": [{"finish_reason": "stop", "message": {"content": '{"answer":"","limitations":[]}'}}]},
    {"choices": [{"finish_reason": "length", "message": {"content": '{"answer":"ok","limitations":[]}'}}]},
    {"choices": []},
    {"choices": [{"finish_reason": "stop", "message": {"content": ""}}]},
    {"choices": [{"finish_reason": "stop", "message": {"content": "{invalid json"}}]},
])
def test_invalid_output(transport, payload):
    transport[0].return_value = httpx.Response(200, json=payload)
    with closing(DeepSeekGenerator("private-key")) as generator:
        with pytest.raises(GenerationError) as caught:
            generator.generate("question")
    assert caught.value.cause is GenerationErrorCause.INVALID_OUTPUT


@pytest.mark.parametrize("status,cause", [
    (408, GenerationErrorCause.TIMEOUT), (429, GenerationErrorCause.RATE_LIMIT),
    (401, GenerationErrorCause.AUTHENTICATION), (403, GenerationErrorCause.AUTHENTICATION),
    (402, GenerationErrorCause.PROVIDER_UNAVAILABLE),
    (503, GenerationErrorCause.PROVIDER_UNAVAILABLE),
    (400, GenerationErrorCause.UNKNOWN),
])
def test_http_errors_are_safe(transport, status, cause):
    transport[0].return_value = httpx.Response(status, json={"error": "private-provider-body"})
    with closing(DeepSeekGenerator("private-key")) as generator:
        with pytest.raises(GenerationError) as caught:
            generator.generate("private-question")
    assert caught.value.cause is cause
    assert "private" not in str(caught.value)
    assert transport[0].call_count == 1


@pytest.mark.parametrize("error,cause", [
    (httpx.ReadTimeout("private-provider-body"), GenerationErrorCause.TIMEOUT),
    (httpx.ConnectError("private-provider-body"), GenerationErrorCause.PROVIDER_UNAVAILABLE),
    (RuntimeError("private-provider-body"), GenerationErrorCause.UNKNOWN),
])
def test_transport_errors_are_safe(transport, error, cause):
    transport[0].side_effect = error
    with closing(DeepSeekGenerator("private-key")) as generator:
        with pytest.raises(GenerationError) as caught:
            generator.generate("private-question")
    assert caught.value.cause is cause
    assert "private" not in str(caught.value)
    assert transport[0].call_count == 1


def test_factory_selects_both_providers(monkeypatch):
    gemini = Mock()
    deepseek = Mock()
    monkeypatch.setattr("evidenceops.gemini.GeminiGenerator", gemini)
    monkeypatch.setattr("evidenceops.deepseek.DeepSeekGenerator", deepseek)
    settings = GenerationSettings(_env_file=None, gemini_api_key="gemini-key")
    assert create_generator(settings) is gemini.return_value
    settings = GenerationSettings(_env_file=None, llm_provider="deepseek", deepseek_api_key="deepseek-key")
    assert create_generator(settings) is deepseek.return_value
    assert deepseek.call_args.kwargs["model"] == "deepseek-flash"


def test_environment_selects_deepseek(monkeypatch):
    monkeypatch.setenv("EVIDENCEOPS_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("EVIDENCEOPS_DEEPSEEK_API_KEY", "private-key")
    settings = GenerationSettings(_env_file=None)
    assert settings.llm_provider == "deepseek"
    assert settings.deepseek_api_key.get_secret_value() == "private-key"
    assert settings.selected_model == "deepseek-flash"


def test_invalid_provider_fails_clearly():
    with pytest.raises(ValidationError, match="llm_provider"):
        GenerationSettings(_env_file=None, llm_provider="invalid")


@pytest.mark.parametrize("failed", [False, True])
def test_event_includes_safe_provider_metadata(transport, caplog, failed):
    if failed:
        transport[0].return_value = httpx.Response(503, json={"error": "private-provider-body"})
    with caplog.at_level(logging.INFO, logger="evidenceops.deepseek"):
        with closing(DeepSeekGenerator("private-key", model="test-model")) as generator:
            if failed:
                with pytest.raises(GenerationError):
                    generator.generate("private-question")
            else:
                generator.generate("private-question")
    events = [json.loads(JsonFormatter().format(record)) for record in caplog.records
              if record.name == "evidenceops.deepseek"]
    assert len(events) == 1
    assert events[0]["event"] == "llm.generation.started"
    assert events[0]["provider"] == "deepseek"
    assert events[0]["model"] == "test-model"
    assert all(value not in json.dumps(events) for value in
               ("private-key", "private-question", "private-provider-body",
                "Respuesta", "limitations"))


def test_http_contract_with_deepseek_adapter(transport):
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from evidenceops.main import create_app, get_generator, get_question_text

    with closing(DeepSeekGenerator("private-key")) as generator:
        app = create_app()
        app.dependency_overrides[get_generator] = lambda: generator
        app.dependency_overrides[get_question_text] = lambda: "private-question"
        response = TestClient(app).post(f"/questions/{uuid4()}/generate")
    assert response.status_code == 200
    assert response.json() == {
        "answer": "Respuesta", "limitations": [], "external_sources_consulted": False,
    }

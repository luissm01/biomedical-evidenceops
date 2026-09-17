"""Exercise the real SDK serialization with an in-memory HTTP transport."""

import runpy
from pathlib import Path
import json
from contextlib import closing
from unittest.mock import Mock

import httpx
import pytest
from google import genai
from pydantic import ValidationError

from evidenceops.gemini import GeminiGenerator, SYSTEM_INSTRUCTION
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause, Generator


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch):
    handler = Mock(return_value=httpx.Response(200, json={
        "id": "simulated-interaction",
        "status": "completed",
        "steps": [{"type": "model_output", "content": [{
            "type": "text",
            "text": '{"answer":"  Respuesta prudente.  ","limitations":[]}',
        }]}],
    }))
    real_client = genai.Client
    clients = []

    def make_client(**kwargs):
        options = kwargs["http_options"]
        options.client_args = {"transport": httpx.MockTransport(handler)}
        client = real_client(**kwargs)
        client.close = Mock(wraps=client.close)
        clients.append(client)
        return client

    monkeypatch.setattr("evidenceops.gemini.genai.Client", make_client)
    yield handler, clients
    for client in clients:
        client.close()


def test_request_response_reuse_and_close(transport) -> None:
    handler, clients = transport
    with closing(GeminiGenerator(
        api_key="test-only-key", model="test-model", max_output_tokens=123,
        timeout_seconds=7.5,
    )) as generator:
        assert handler.call_count == 0  # No inference at construction.
        contract: Generator = generator
        for question in ["Primera pregunta", "Segunda pregunta"]:
            result = contract.generate(question)
            assert result == GeneratedContent(answer="Respuesta prudente.", limitations=[])
            request = handler.call_args.args[0]
            body = json.loads(request.content)
            assert body["model"] == "test-model"
            assert body["input"] == question
            assert body["system_instruction"] == SYSTEM_INSTRUCTION
            assert body["generation_config"]["max_output_tokens"] == 123
            assert body["store"] is False
            assert body["response_format"]["schema"] == GeneratedContent.model_json_schema()
            assert body["response_format"]["mime_type"] == "application/json"
            assert "external_sources_consulted" not in body["response_format"]["schema"]["properties"]
            assert request.headers["x-goog-api-key"] == "test-only-key"
            assert request.extensions["timeout"]["read"] == 7.5
        assert len(clients) == 1
        clients[0].close.assert_not_called()
    clients[0].close.assert_called_once()
    assert handler.call_count == 2


@pytest.mark.parametrize("text", [
    None, "", "not-json", '{"answer":',
    '{"answer":"   ","limitations":[]}',
    '{"answer":"Respuesta","limitations":[" "]}',
    '{"answer":"Respuesta","limitations":"incorrect"}',
    '{"limitations":[]}',
])
def test_invalid_output_is_application_error(transport, text) -> None:
    handler, _ = transport
    handler.return_value = httpx.Response(200, json={
        "status": "completed",
        "steps": [] if text is None else [{
            "type": "model_output",
            "content": [{"type": "text", "text": text}],
        }],
    })
    with closing(GeminiGenerator(api_key="test-only-key")) as generator:
        with pytest.raises(GenerationError) as caught:
            generator.generate("Pregunta")
    assert caught.value.cause is GenerationErrorCause.INVALID_OUTPUT
    assert isinstance(caught.value.__cause__, ValidationError)
    assert handler.call_count == 1


@pytest.mark.parametrize("status,cause,attempts", [
    (400, GenerationErrorCause.UNKNOWN, 1),
    (401, GenerationErrorCause.AUTHENTICATION, 1),
    (403, GenerationErrorCause.AUTHENTICATION, 1),
    (408, GenerationErrorCause.TIMEOUT, 2),
    (429, GenerationErrorCause.RATE_LIMIT, 1),
    (500, GenerationErrorCause.PROVIDER_UNAVAILABLE, 2),
    (502, GenerationErrorCause.PROVIDER_UNAVAILABLE, 2),
    (503, GenerationErrorCause.PROVIDER_UNAVAILABLE, 2),
    (504, GenerationErrorCause.PROVIDER_UNAVAILABLE, 2),
    (501, GenerationErrorCause.PROVIDER_UNAVAILABLE, 1),
])
def test_provider_errors_and_retry_policy(transport, monkeypatch, status, cause, attempts):
    sleep = Mock()
    monkeypatch.setattr("time.sleep", sleep)
    handler, _ = transport
    handler.return_value = httpx.Response(status, json={
        "error": {"code": status, "message": "provider detail test-only-key"},
    })
    with closing(GeminiGenerator(api_key="test-only-key")) as generator:
        with pytest.raises(GenerationError) as caught:
            generator.generate("Pregunta")
    assert caught.value.cause is cause
    assert caught.value.__cause__ is not None
    assert handler.call_count == attempts
    assert "test-only-key" not in str(caught.value)
    assert "provider detail" not in str(caught.value)
    if attempts == 2:
        sleep.assert_called_once_with(0.5)
    else:
        sleep.assert_not_called()


@pytest.mark.parametrize("exception,cause,attempts", [
    (httpx.ReadTimeout, GenerationErrorCause.TIMEOUT, 1),
    (httpx.ConnectTimeout, GenerationErrorCause.TIMEOUT, 1),
    (httpx.ConnectError, GenerationErrorCause.PROVIDER_UNAVAILABLE, 1),
    (RuntimeError, GenerationErrorCause.UNKNOWN, 1),
])
def test_transport_errors(transport, monkeypatch, exception, cause, attempts):
    sleep = Mock()
    monkeypatch.setattr("time.sleep", sleep)
    handler, _ = transport
    handler.side_effect = exception("provider detail test-only-key")
    with closing(GeminiGenerator(api_key="test-only-key")) as generator:
        with pytest.raises(GenerationError) as caught:
            generator.generate("Pregunta")
    assert caught.value.cause is cause
    assert handler.call_count == attempts
    assert sleep.call_count == attempts - 1
    assert "test-only-key" not in str(caught.value)
    assert "provider detail" not in str(caught.value)


@pytest.mark.parametrize("status,attempts", [(429, 1), (503, 2)])
def test_retry_after_behavior(transport, monkeypatch, status, attempts):
    sleep = Mock()
    monkeypatch.setattr("time.sleep", sleep)
    handler, _ = transport
    handler.return_value = httpx.Response(
        status, headers={"Retry-After": "30"}, json={"error": {"code": status}},
    )
    with closing(GeminiGenerator(api_key="test-only-key")) as generator:
        with pytest.raises(GenerationError):
            generator.generate("Pregunta")
    assert handler.call_count == attempts
    if status == 503:
        # SDK honors Retry-After even above max_delay; it is not a total deadline.
        sleep.assert_called_once_with(30.0)
    else:
        sleep.assert_not_called()


def test_transient_failure_then_success(transport, monkeypatch):
    sleep = Mock()
    monkeypatch.setattr("time.sleep", sleep)
    handler, _ = transport
    handler.side_effect = [httpx.Response(503, json={}), handler.return_value]
    with closing(GeminiGenerator(api_key="test-only-key")) as generator:
        result = generator.generate("Pregunta")
    assert result == GeneratedContent(answer="Respuesta prudente.", limitations=[])
    assert handler.call_count == 2
    sleep.assert_called_once_with(0.5)


@pytest.mark.parametrize("key", ["", " \t "])
def test_missing_key_fails_before_client_creation(monkeypatch, key) -> None:
    client = Mock()
    monkeypatch.setattr("evidenceops.gemini.genai.Client", client)
    with pytest.raises(ValueError, match="EVIDENCEOPS_GEMINI_API_KEY"):
        GeminiGenerator(api_key=key)
    client.assert_not_called()


def test_manual_script_import_does_not_infer(monkeypatch) -> None:
    client = Mock(side_effect=AssertionError("Manual inference during import"))
    monkeypatch.setattr("evidenceops.gemini.genai.Client", client)
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "test_gemini.py"))
    client.assert_not_called()


@pytest.mark.parametrize("provider_status,http_status", [(200, 200), (503, 503)])
def test_http_database_and_real_adapter_flow(
    transport, client, fake_generator, monkeypatch, provider_status, http_status
):
    monkeypatch.setattr("time.sleep", Mock())
    handler, _ = transport
    if provider_status != 200:
        handler.return_value = httpx.Response(provider_status, json={"error": {"code": provider_status}})
    created = client.post("/questions", json={"text": "Pregunta de integración"})
    with closing(GeminiGenerator(api_key="test-only-key")) as generator:
        monkeypatch.setattr(fake_generator, "generate", generator.generate)
        response = client.post(f"/questions/{created.json()['id']}/generate")
    assert response.status_code == http_status
    assert json.loads(handler.call_args.args[0].content)["input"] == "Pregunta de integración"
    if http_status == 200:
        assert response.json() == {
            "answer": "Respuesta prudente.", "limitations": [],
            "external_sources_consulted": False,
        }
    else:
        assert response.json()["detail"]["code"] == "generation_unavailable"

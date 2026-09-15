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
        "status": "completed", "output_text": text,
    })
    with closing(GeminiGenerator(api_key="test-only-key")) as generator:
        with pytest.raises(GenerationError) as caught:
            generator.generate("Pregunta")
    assert caught.value.cause is GenerationErrorCause.INVALID_OUTPUT
    assert isinstance(caught.value.__cause__, ValidationError)


def test_sdk_retry_behavior_and_safe_error(transport, monkeypatch) -> None:
    sleep = Mock()
    monkeypatch.setattr("time.sleep", sleep)
    handler, clients = transport
    handler.return_value = httpx.Response(503, json={
        "error": {"code": 503, "message": "provider detail test-only-key"},
    })
    with pytest.raises(GenerationError) as caught:
        with closing(GeminiGenerator(api_key="test-only-key")) as generator:
            generator.generate("Pregunta")
    assert caught.value.cause is GenerationErrorCause.UNKNOWN
    assert caught.value.__cause__ is not None
    assert "test-only-key" not in str(caught.value)
    assert "provider detail" not in str(caught.value)
    # google-genai 2.23.0 normalizes attempts=0 to 1, then Interactions
    # interprets it as one retry. Track this until #11 resolves the policy.
    assert handler.call_count == 2
    sleep.assert_called_once()
    clients[0].close.assert_called_once()


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

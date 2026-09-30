"""HTTP correlation and actual JSON output, without database or provider access."""

import asyncio
import json
import logging
import math
import io
import sys
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from evidenceops.database import get_session
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause
from evidenceops.main import create_app, get_generator, get_question_text
from evidenceops.observability import (
    RequestContextMiddleware, configure_logging, request_id,
)


@pytest.fixture
def events(monkeypatch):
    logger = logging.getLogger("evidenceops")
    previous = logger.handlers[:], logger.level, logger.propagate
    logger.handlers = []
    stream = io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", stream)
        configure_logging()
    def read():
        output = [json.loads(line) for line in stream.getvalue().splitlines()]
        stream.seek(0)
        stream.truncate()
        return output
    yield read
    for handler in logger.handlers:
        handler.close()
    logger.handlers, logger.level, logger.propagate = previous


def client_for(generator):
    app = create_app()
    app.dependency_overrides[get_question_text] = lambda: "private-question"
    app.dependency_overrides[get_generator] = lambda: generator
    app.dependency_overrides[get_session] = lambda: None
    # No lifespan: these tests replace the database and generator dependencies.
    return TestClient(app, raise_server_exceptions=False)


class Generator:
    def generate(self, question_text):
        logging.getLogger("evidenceops.test").info("test.inside_generator")
        return GeneratedContent(answer="private-answer", limitations=["private-limitation"])


def test_success_correlation_privacy_and_distinct_ids(events):
    client = client_for(Generator())
    ids = []
    for _ in range(2):
        response = client.post(f"/questions/{uuid4()}/generate", headers={"X-Request-ID": "untrusted"})
        assert response.status_code == 200
        assert response.json() == {"answer": "private-answer", "limitations": ["private-limitation"],
                                   "external_sources_consulted": False}
        identifier = response.headers["X-Request-ID"]
        UUID(identifier)
        ids.append(identifier)
        output = events()
        assert [item["event"] for item in output] == [
            "generation.started", "test.inside_generator", "generation.succeeded"]
        assert {item["request_id"] for item in output} == {identifier}
        assert all(item["level"] == "INFO" for item in output)
        assert math.isfinite(output[-1]["duration_ms"]) and output[-1]["duration_ms"] >= 0
        assert output[-1]["outcome"] == "success"
        assert "private-" not in json.dumps(output)
    assert ids[0] != ids[1]
    logging.getLogger("evidenceops.test").info("outside")
    assert events()[0]["request_id"] is None


@pytest.mark.parametrize("cause,status", [
    (GenerationErrorCause.TIMEOUT, 504), (GenerationErrorCause.RATE_LIMIT, 429),
    (GenerationErrorCause.AUTHENTICATION, 503),
    (GenerationErrorCause.PROVIDER_UNAVAILABLE, 503),
    (GenerationErrorCause.INVALID_OUTPUT, 502), (GenerationErrorCause.UNKNOWN, 502),
])
def test_safe_failure(events, cause, status):
    class FailingGenerator:
        def generate(self, question_text):
            raise GenerationError(cause, "private-key provider-body") from RuntimeError("private-chain")
    response = client_for(FailingGenerator()).post(f"/questions/{uuid4()}/generate")
    assert response.status_code == status
    output = events()
    assert [item["event"] for item in output] == ["generation.started", "generation.failed"]
    assert {item["request_id"] for item in output} == {response.headers["X-Request-ID"]}
    assert output[-1]["cause"] == cause.value
    assert output[-1]["level"] == "WARNING"
    assert output[-1]["outcome"] == "error"
    assert math.isfinite(output[-1]["duration_ms"]) and output[-1]["duration_ms"] >= 0
    assert "private-" not in json.dumps(output)


def test_unexpected_error_preserves_500_and_header(events):
    class BrokenGenerator:
        def generate(self, question_text):
            raise RuntimeError("private-error")
    response = client_for(BrokenGenerator()).post(f"/questions/{uuid4()}/generate")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    output = events()
    assert output[-1]["request_id"] == response.headers["X-Request-ID"]
    assert output[-1]["level"] == "ERROR"
    assert output[-1]["cause"] == "unexpected_application_error"
    assert "private-error" not in json.dumps(output)


def test_non_generation_requests_have_ids_without_generation_events(events):
    client = client_for(Generator())
    responses = [client.get("/health"), client.get("/missing"),
                 client.post("/questions", json={"text": ""})]
    assert [r.status_code for r in responses] == [200, 404, 422]
    assert len({r.headers["X-Request-ID"] for r in responses}) == 3
    assert events() == []


def test_context_isolated_concurrently_and_restored_after_exception():
    async def run():
        barrier = asyncio.Event()
        seen = []
        async def app(scope, receive, send):
            seen.append(request_id.get())
            if len(seen) == 2:
                barrier.set()
            await barrier.wait()
            before = request_id.get()
            await asyncio.sleep(0)
            assert request_id.get() == before
            raise RuntimeError("test")
        middleware = RequestContextMiddleware(app)
        async def request():
            assert request_id.get() is None
            with pytest.raises(RuntimeError):
                await middleware({"type": "http"}, None, None)
            assert request_id.get() is None
        await asyncio.gather(request(), request())
        assert len(set(seen)) == 2
    asyncio.run(run())


def test_formatter_ignores_exception_and_unapproved_fields(events):
    try:
        raise ValueError("private-exception")
    except ValueError:
        logging.getLogger("evidenceops.test").warning(
            "safe.event", exc_info=True, extra={"question": "private-question", "api_key": "private-key"})
    assert "private-" not in json.dumps(events())


def test_configuration_does_not_duplicate_events(events):
    configure_logging()
    configure_logging()
    logging.getLogger("evidenceops.test").info("once")
    assert len(events()) == 1


@pytest.mark.parametrize("failed", [False, True])
def test_http_and_gemini_share_id_without_provider_content(events, monkeypatch, failed):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from evidenceops.gemini import GeminiGenerator

    create = Mock(return_value=SimpleNamespace(
        output_text='{"answer":"private-answer","limitations":["private-limitation"]}'))
    if failed:
        create.side_effect = RuntimeError("private-provider-body private-key")
    sdk = SimpleNamespace(interactions=SimpleNamespace(create=create), close=Mock())
    monkeypatch.setattr("evidenceops.gemini.genai.Client", Mock(return_value=sdk))
    generator = GeminiGenerator(api_key="private-key", model="test-model")
    try:
        response = client_for(generator).post(f"/questions/{uuid4()}/generate")
    finally:
        generator.close()
    assert response.status_code == (502 if failed else 200)
    output = events()
    assert [item["event"] for item in output] == [
        "generation.started", "llm.generation.started",
        "generation.failed" if failed else "generation.succeeded",
    ]
    assert {item["request_id"] for item in output} == {response.headers["X-Request-ID"]}
    assert output[1]["model"] == "test-model"
    assert output[1]["provider"] == "gemini"
    assert "private-" not in json.dumps(output)

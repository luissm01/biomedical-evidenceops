from uuid import uuid4
import pytest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from evidenceops.generation import GenerationError, GenerationErrorCause


def test_generate_answer_for_existing_question(
    client: TestClient,
    fake_generator,
) -> None:
    create_response = client.post(
        "/questions",
        json={"text": "¿Qué es un ensayo clínico aleatorizado?"},
    )

    question_id = create_response.json()["id"]

    response = client.post(
        f"/questions/{question_id}/generate"
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Respuesta generada para el test",
        "limitations": ["Limitación de prueba"],
        "external_sources_consulted": False,
    }

    assert fake_generator.calls == [
        "¿Qué es un ensayo clínico aleatorizado?"
    ]


def test_generate_answer_for_missing_question_does_not_call_generator(
    client: TestClient,
    fake_generator,
) -> None:
    response = client.post(
        f"/questions/{uuid4()}/generate"
    )

    assert response.status_code == 404
    assert fake_generator.calls == []


def test_generate_answer_with_invalid_uuid_does_not_call_generator(
    client: TestClient,
    fake_generator,
) -> None:
    response = client.post(
        "/questions/not-a-uuid/generate"
    )

    assert response.status_code == 422
    assert fake_generator.calls == []


def test_database_connection_is_released_before_generation(
    client: TestClient, fake_generator, monkeypatch
) -> None:
    created = client.post("/questions", json={"text": "Pregunta persistida"})
    engine = client.app.state.session_factory.kw["bind"]
    generate = fake_generator.generate

    def generate_after_release(question_text):
        assert engine.pool.checkedout() == 0
        return generate(question_text)

    monkeypatch.setattr(fake_generator, "generate", generate_after_release)
    response = client.post(f"/questions/{created.json()['id']}/generate")
    assert response.status_code == 200
    assert fake_generator.calls == ["Pregunta persistida"]


@pytest.mark.parametrize("cause,status,code,message", [
    (GenerationErrorCause.TIMEOUT, 504, "generation_timeout",
     "Generation did not complete in time"),
    (GenerationErrorCause.RATE_LIMIT, 429, "generation_rate_limited",
     "Generation is temporarily rate limited"),
    (GenerationErrorCause.AUTHENTICATION, 503, "generation_unavailable",
     "Generation service is unavailable"),
    (GenerationErrorCause.PROVIDER_UNAVAILABLE, 503, "generation_unavailable",
     "Generation service is unavailable"),
    (GenerationErrorCause.INVALID_OUTPUT, 502, "invalid_generation",
     "Generation service returned an invalid response"),
    (GenerationErrorCause.UNKNOWN, 502, "generation_failed",
     "Generation could not be completed"),
])
def test_generation_errors_are_safe_http_responses(
    client, fake_generator, monkeypatch, cause, status, code, message
):
    created = client.post("/questions", json={"text": "Pregunta persistida"})
    error = GenerationError(cause, "private provider detail test-only-key")
    error.__cause__ = RuntimeError("private chained details")
    generate = Mock(side_effect=error)
    monkeypatch.setattr(fake_generator, "generate", generate)
    response = client.post(f"/questions/{created.json()['id']}/generate")
    assert response.status_code == status
    assert response.json() == {"detail": {"code": code, "message": message}}
    generate.assert_called_once_with("Pregunta persistida")
    assert client.get(created.headers["Location"]).json() == created.json()

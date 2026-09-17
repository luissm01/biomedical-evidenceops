from uuid import uuid4
from fastapi.testclient import TestClient


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

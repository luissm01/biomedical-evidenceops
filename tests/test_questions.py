from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from evidenceops.config import Settings
from evidenceops.main import create_app


def test_create_and_retrieve_question(client: TestClient) -> None:
    text = "¿Qué evidencia existe sobre la intervención X?"
    created = client.post("/questions", json={"text": f"  {text}\n"})

    assert created.status_code == 201
    body = created.json()
    assert set(body) == {"id", "text"}
    assert UUID(body["id"]).version == 4
    assert body["text"] == text
    assert created.headers["Location"] == f"/questions/{body['id']}"

    retrieved = client.get(created.headers["Location"])

    assert retrieved.status_code == 200
    assert retrieved.json() == body


def test_repeated_text_creates_distinct_questions(client: TestClient) -> None:
    payload = {"text": "¿Qué evidencia existe sobre la intervención X?"}
    first = client.post("/questions", json=payload)
    second = client.post("/questions", json=payload)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    for created in (first, second):
        retrieved = client.get(created.headers["Location"])
        assert retrieved.status_code == 200
        assert retrieved.json() == created.json()


def test_question_survives_application_restart(
    test_settings: Settings, clean_questions: None
) -> None:
    with TestClient(create_app(test_settings)) as first_client:
        created = first_client.post("/questions", json={"text": "Persistente"})

    with TestClient(create_app(test_settings)) as restarted_client:
        retrieved = restarted_client.get(created.headers["Location"])

    assert retrieved.status_code == 200
    assert retrieved.json() == created.json()


@pytest.mark.parametrize("text", ["x", "x" * 2000])
def test_accepts_text_length_boundaries(client: TestClient, text: str) -> None:
    response = client.post("/questions", json={"text": text})

    assert response.status_code == 201
    assert response.json()["text"] == text


@pytest.mark.parametrize(
    "payload, field",
    [
        ({}, "text"),
        ({"text": ""}, "text"),
        ({"text": " \t\n "}, "text"),
        ({"text": "x" * 2001}, "text"),
        ({"text": None}, "text"),
        ({"text": 123}, "text"),
        ({"text": True}, "text"),
        ({"text": []}, "text"),
        ({"text": "Pregunta", "id": str(uuid4())}, "id"),
    ],
)
def test_rejects_invalid_question(
    client: TestClient, payload: dict[str, object], field: str
) -> None:
    response = client.post("/questions", json=payload)

    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", field] for error in response.json()["detail"]
    )


def test_unknown_question_returns_not_found(client: TestClient) -> None:
    response = client.get(f"/questions/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Question not found"}


def test_invalid_question_id_returns_validation_error(client: TestClient) -> None:
    response = client.get("/questions/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "question_id"]

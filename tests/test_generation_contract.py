import pytest
from pydantic import ValidationError

from evidenceops.generation import GeneratedContent


def test_valid_generated_content_allows_no_specific_limitations() -> None:
    content = GeneratedContent(answer="  Respuesta prudente.  ", limitations=[])

    assert content.answer == "Respuesta prudente."
    assert content.limitations == []


@pytest.mark.parametrize(
    "payload",
    [
        {"answer": " \t ", "limitations": []},
        {"answer": "Respuesta", "limitations": ["  "]},
        {"answer": "Respuesta", "limitations": "No hay fuentes externas"},
        {"answer": "Respuesta"},
    ],
)
def test_invalid_generated_content_is_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GeneratedContent.model_validate(payload)

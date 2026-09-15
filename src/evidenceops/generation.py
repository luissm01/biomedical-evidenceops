"""Provider-neutral contract for generating an answer to a stored question."""

from enum import StrEnum
from typing import Annotated, Protocol

from pydantic import BaseModel, Field, StringConstraints


type NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GeneratedContent(BaseModel):
    answer: NonEmptyText = Field(
        description="Clear and prudent answer to the biomedical question."
    )
    limitations: list[NonEmptyText] = Field(
        description=(
            "Relevant limitations of the answer or missing "
            "information in the question."
        )
    )


class GenerationErrorCause(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_OUTPUT = "invalid_output"
    UNKNOWN = "unknown"


class GenerationError(RuntimeError):
    def __init__(
        self,
        cause: GenerationErrorCause,
        message: str,
    ) -> None:
        super().__init__(message)
        self.cause = cause


class Generator(Protocol):
    def generate(self, question_text: str) -> GeneratedContent:
        ...

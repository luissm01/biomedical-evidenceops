"""Safe typed failures for the RAG orchestration boundary."""

from typing import Literal

from evidenceops.generation import GenerationError, GenerationErrorCause


type CitationFailureReason = Literal[
    "unknown_citation", "malformed_citation", "block_missing_citation",
    "block_not_cited_at_end", "invalid_abstention",
]
type CitationField = Literal["answer", "limitations"]


class RagRetrievalError(RuntimeError):
    def __init__(self, cause: str) -> None:
        super().__init__("RAG retrieval is unavailable")
        self.cause = cause


class InvalidCitationsError(GenerationError):
    """INVALID_OUTPUT specifically from deterministic RAG citation validation."""

    def __init__(
        self,
        reason: CitationFailureReason,
        field: CitationField,
        *,
        limitation_index: int | None = None,
        block_index: int | None = None,
        character_offset: int | None = None,
    ) -> None:
        super().__init__(
            GenerationErrorCause.INVALID_OUTPUT,
            "RAG output contains invalid citations or uncited content",
        )
        # Store only codes and numeric locations, never model output or citation text.
        self.reason = reason
        self.field = field
        self.limitation_index = limitation_index
        self.block_index = block_index
        self.character_offset = character_offset

    def diagnostic(self) -> dict[str, str | int]:
        fields: dict[str, str | int | None] = {
            "validation_reason": self.reason,
            "validation_field": self.field,
            "limitation_index": self.limitation_index,
            "block_index": self.block_index,
            "character_offset": self.character_offset,
        }
        return {key: value for key, value in fields.items() if value is not None}

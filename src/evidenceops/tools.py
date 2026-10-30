"""Two bounded read tools. No provider, agent, HTTP endpoint or ingestion."""

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
import json
from time import monotonic
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, TimeoutError as SQLTimeoutError

from evidenceops.biomedical import BiomedicalDocument
from evidenceops.embeddings import MedCPTEncoder
from evidenceops.publications import get_publication
from evidenceops.retrieval import RetrievalResult, search

ARGUMENT_CHARACTER_LIMIT = 4_000
RESULT_CHARACTER_LIMIT = 20_000
TOOL_BUDGET_SECONDS = 15.0
SQL_TIMEOUT_MS = 5_000
type ToolName = Literal["search_evidence", "get_publication"]
type Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class SearchEvidenceArgs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    query: Query
    top_k: int = Field(default=5, ge=1, le=5)
    published_from: int | None = Field(default=None, gt=0)


class GetPublicationArgs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    publication_id: UUID

    @field_validator("publication_id", mode="before")
    @classmethod
    def parse_identifier(cls, value: object) -> UUID:
        if not isinstance(value, str):
            raise ValueError("publication_id must be a UUID string")
        return UUID(value)


@dataclass(frozen=True)
class ToolDefinition:
    name: ToolName
    description: str
    arguments: type[SearchEvidenceArgs] | type[GetPublicationArgs]


TOOL_DEFINITIONS = (
    ToolDefinition("search_evidence", "Discover publications in the local indexed corpus. "
        "Returns bibliographic metadata only, NOT abstracts or clinical findings. "
        "Scores rank results; they are not clinical confidence. No PubMed/network access.", SearchEvidenceArgs),
    ToolDefinition("get_publication", "Read bibliographic details and the complete available abstract "
        "of one local publication by its internal UUID, NOT its PMID. Does not fetch full text "
        "or access PubMed. A publication may have no abstract.", GetPublicationArgs),
)


class ToolCall(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True, frozen=True)
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
    arguments: str  # Raw JSON: executor, not the model adapter, validates arguments.


class PublicationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    citation_id: str
    publication_id: UUID
    source: str
    source_id: str
    title: str
    publication_year: int | None
    journal: str | None
    doi: str | None
    source_url: str | None


class EvidenceHit(PublicationMetadata):
    detail_level: Literal["metadata"] = "metadata"
    unit_id: str
    content_fingerprint: str
    score: float = Field(allow_inf_nan=False)


class PublicationDetails(PublicationMetadata):
    detail_level: Literal["abstract"] = "abstract"
    authors: list[str]
    abstract: str | None


class SearchEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    items: list[EvidenceHit] = Field(max_length=5)


class ToolErrorBody(BaseModel):
    code: Literal["publication_not_found"] = "publication_not_found"
    message: str = "Publication does not exist in the local corpus"


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    call_id: str
    tool: ToolName
    status: Literal["ok", "error"]
    data: SearchEvidenceData | PublicationDetails | None = None
    error: ToolErrorBody | None = None

    @model_validator(mode="after")
    def coherent_result(self):
        if self.status == "error":
            if self.tool != "get_publication" or self.error is None or self.data is not None:
                raise ValueError("Only a missing publication is a domain error result")
        elif self.error is not None or not isinstance(
            self.data, SearchEvidenceData if self.tool == "search_evidence" else PublicationDetails,
        ):
            raise ValueError("Tool result does not match its declared tool")
        return self

    def payload(self) -> dict:
        # Preserve null bibliographic fields, especially a missing abstract.
        return self.model_dump(mode="json", exclude={"error"} if self.status == "ok" else {"data"})

    def sources(self) -> tuple[PublicationMetadata, ...]:
        if self.status != "ok":
            return ()
        if isinstance(self.data, SearchEvidenceData):
            return tuple(self.data.items)
        return () if self.data is None else (self.data,)


type ToolErrorCode = Literal[
    "unknown_tool", "invalid_arguments", "invalid_call", "call_limit_exceeded",
    "round_limit_exceeded", "sql_timeout", "tool_timeout", "tool_budget_exceeded",
    "backend_error", "result_too_large", "invalid_references",
]


class ToolCallingError(RuntimeError):
    def __init__(self, code: ToolErrorCode):
        # Fixed message, never include model arguments or dependency exception text.
        super().__init__(f"Tool calling failed: {code}")
        self.code = code


class ToolExecutor:
    """Only registered operations; injected backends own no LLM state.

    The elapsed budget is cooperative: CPU work is not forcibly interrupted.
    Effective SQL timeouts are installed separately by create_tool_executor.
    """

    def __init__(self, retrieve: Callable[..., list[RetrievalResult]],
                 lookup: Callable[[UUID], BiomedicalDocument | None], *,
                 clock: Callable[[], float] = monotonic):
        self._retrieve = retrieve
        self._lookup = lookup
        self._clock = clock
        self._registry = {definition.name: definition for definition in TOOL_DEFINITIONS}

    def validate(self, call: ToolCall) -> SearchEvidenceArgs | GetPublicationArgs:
        if call.name not in self._registry:
            raise ToolCallingError("unknown_tool")
        if len(call.arguments) > ARGUMENT_CHARACTER_LIMIT:
            raise ToolCallingError("invalid_arguments")
        try:
            # Reject duplicate keys rather than silently using the last value.
            arguments = json.loads(call.arguments, object_pairs_hook=_unique_object)
            return self._registry[call.name].arguments.model_validate(arguments)
        except (ValueError, TypeError, RecursionError, ValidationError) as exc:
            raise ToolCallingError("invalid_arguments") from exc

    def execute(self, call: ToolCall) -> ToolResult:
        arguments = self.validate(call)
        started = self._clock()
        try:
            if isinstance(arguments, SearchEvidenceArgs):
                results = self._retrieve(**arguments.model_dump())
                if len(results) > arguments.top_k:
                    raise ToolCallingError("backend_error")
                items = []
                for index, result in enumerate(results, 1):
                    unit = result.unit
                    items.append(EvidenceHit(
                        citation_id=f"S{index}", publication_id=unit.publication_id,
                        source=unit.source, source_id=unit.source_id, title=unit.title,
                        publication_year=unit.publication_year, journal=unit.journal,
                        doi=unit.doi, source_url=unit.source_url, unit_id=unit.unit_id,
                        content_fingerprint=unit.content_fingerprint, score=result.score,
                    ))
                result = ToolResult(call_id=call.id, tool="search_evidence", status="ok",
                                    data=SearchEvidenceData(items=items))
            else:
                document = self._lookup(arguments.publication_id)
                if document is None:
                    result = ToolResult(call_id=call.id, tool="get_publication", status="error",
                                        error=ToolErrorBody())
                else:
                    result = ToolResult(call_id=call.id, tool="get_publication", status="ok",
                        data=PublicationDetails(citation_id="S1", publication_id=arguments.publication_id,
                            source=document.source, source_id=document.source_id, title=document.title,
                            publication_year=document.publication_year, journal=document.journal,
                            doi=document.doi, source_url=document.source_url, authors=document.authors,
                            abstract=document.abstract))
            if self._clock() - started > TOOL_BUDGET_SECONDS:
                raise ToolCallingError("tool_budget_exceeded")
            if len(compact_json(result.payload())) > RESULT_CHARACTER_LIMIT:
                raise ToolCallingError("result_too_large")
            return result
        except ToolCallingError:
            raise
        except (TimeoutError, SQLTimeoutError) as exc:
            raise ToolCallingError("tool_timeout") from exc
        except DBAPIError as exc:
            code = "sql_timeout" if getattr(exc.orig, "sqlstate", None) == "57014" else "backend_error"
            raise ToolCallingError(code) from exc
        except Exception as exc:
            raise ToolCallingError("backend_error") from exc


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON key")
        result[name] = value
    return result


def create_tool_executor(sessions, encoder: MedCPTEncoder) -> ToolExecutor:
    """Compose existing services with short, read-only PostgreSQL transactions."""
    @contextmanager
    def read_session():
        with sessions() as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            session.execute(text(f"SET LOCAL statement_timeout = '{SQL_TIMEOUT_MS}ms'"))
            yield session

    def retrieve(**arguments):
        return search(read_session, encoder, mode="semantic", **arguments)

    def lookup(publication_id):
        with read_session() as session:
            return get_publication(session, publication_id)

    return ToolExecutor(retrieve, lookup)

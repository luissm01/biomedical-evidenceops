from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from evidenceops.rag import RagSource


class HealthCheckResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, str]


class QuestionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(min_length=1, max_length=2000)


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    text: str


class GenerationResponse(BaseModel):
    answer: str
    limitations: list[str]
    external_sources_consulted: Literal[False] = False


class RagRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    # Upper bound keeps the value inside PostgreSQL's integer range (no 500s).
    published_from: int | None = Field(default=None, gt=0, le=9999, strict=True)


class RagHTTPResponse(BaseModel):
    answer: str
    limitations: list[str]
    sources: list[RagSource]


class IngestionJobCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(ge=1, le=100, strict=True)


JobStatusValue = Literal["queued", "running", "succeeded", "failed"]


class IngestionJobAccepted(BaseModel):
    job_id: UUID
    status: JobStatusValue


class IngestionJobResponse(BaseModel):
    job_id: UUID
    status: JobStatusValue
    query: str
    limit: int
    attempts: int
    max_attempts: int
    last_error: str | None
    next_attempt_at: datetime | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result: dict | None

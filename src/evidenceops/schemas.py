from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from evidenceops.rag import RagSource


class HealthCheckResponse(BaseModel):
    status: Literal["ok"]


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
    published_from: int | None = Field(default=None, gt=0, strict=True)


class RagHTTPResponse(BaseModel):
    answer: str
    limitations: list[str]
    sources: list[RagSource]

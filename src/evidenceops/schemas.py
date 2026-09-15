from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthCheckResponse(BaseModel):
    status: Literal["ok"]


class QuestionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(min_length=1, max_length=2000)


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    text: str

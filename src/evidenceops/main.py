from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI()


class HealthCheckResponse(BaseModel):
    status: Literal["ok"]


class QuestionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(min_length=1, max_length=2000)


class QuestionResponse(BaseModel):
    id: UUID
    text: str


# Temporary storage: private to this process and lost on restart.
_questions: dict[UUID, QuestionResponse] = {}


@app.get("/health", response_model=HealthCheckResponse)
def health_check() -> HealthCheckResponse:
    return HealthCheckResponse(status="ok")


@app.post("/questions", status_code=201)
def create_question(question: QuestionCreate, response: Response) -> QuestionResponse:
    created = QuestionResponse(id=uuid4(), text=question.text)
    _questions[created.id] = created
    response.headers["Location"] = f"/questions/{created.id}"
    return created


@app.get("/questions/{question_id}")
def get_question(question_id: UUID) -> QuestionResponse:
    question = _questions.get(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return question

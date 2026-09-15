from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from evidenceops.config import Settings
from evidenceops.database import create_database, get_session
from evidenceops.models import Question
from evidenceops.schemas import HealthCheckResponse, QuestionCreate, QuestionResponse

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse)
def health_check() -> HealthCheckResponse:
    return HealthCheckResponse(status="ok")


@router.post("/questions", response_model=QuestionResponse, status_code=201)
def create_question(
    question: QuestionCreate,
    response: Response,
    session: Session = Depends(get_session),
) -> QuestionResponse:
    created = Question(id=uuid4(), text=question.text)
    session.add(created)
    session.commit()

    response.headers["Location"] = f"/questions/{created.id}"
    return QuestionResponse.model_validate(created)


@router.get("/questions/{question_id}", response_model=QuestionResponse)
def get_question(
    question_id: UUID,
    session: Session = Depends(get_session),
) -> QuestionResponse:
    question = session.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionResponse.model_validate(question)


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configured_settings = settings or Settings()
        engine, session_factory = create_database(configured_settings)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            app.state.session_factory = session_factory
            yield
        finally:
            engine.dispose()

    application = FastAPI(lifespan=lifespan)
    application.include_router(router)
    return application


app = create_app()

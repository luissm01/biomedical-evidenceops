from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from evidenceops.config import Settings
from evidenceops.database import create_database, get_session
from evidenceops.gemini import GeminiGenerator
from evidenceops.generation import (
    GenerationError,
    GenerationErrorCause,
    Generator,
)
from evidenceops.models import Question
from evidenceops.schemas import (
    GenerationResponse,
    HealthCheckResponse,
    QuestionCreate,
    QuestionResponse,
)


_GENERATION_HTTP_ERRORS = {
    GenerationErrorCause.TIMEOUT: (
        504,
        "generation_timeout",
        "Generation did not complete in time",
    ),
    GenerationErrorCause.RATE_LIMIT: (
        429,
        "generation_rate_limited",
        "Generation is temporarily rate limited",
    ),
    GenerationErrorCause.AUTHENTICATION: (
        503,
        "generation_unavailable",
        "Generation service is unavailable",
    ),
    GenerationErrorCause.PROVIDER_UNAVAILABLE: (
        503,
        "generation_unavailable",
        "Generation service is unavailable",
    ),
    GenerationErrorCause.INVALID_OUTPUT: (
        502,
        "invalid_generation",
        "Generation service returned an invalid response",
    ),
    GenerationErrorCause.UNKNOWN: (
        502,
        "generation_failed",
        "Generation could not be completed",
    ),
}


def _generation_http_exception(error: GenerationError) -> HTTPException:
    status_code, code, message = _GENERATION_HTTP_ERRORS[error.cause]

    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
        },
    )


router = APIRouter()


def get_generator(request: Request) -> Generator:
    return cast(Generator, request.app.state.generator)


def get_question_text(question_id: UUID, request: Request) -> str:
    session_factory = cast(
        sessionmaker[Session],
        request.app.state.session_factory,
    )

    with session_factory() as session:
        question = session.get(Question, question_id)

        if question is None:
            raise HTTPException(
                status_code=404,
                detail="Question not found",
            )

        return question.text


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


@router.post(
    "/questions/{question_id}/generate",
    response_model=GenerationResponse,
)
def generate_answer(
    question_text: str = Depends(get_question_text),
    generator: Generator = Depends(get_generator),
) -> GenerationResponse:
    try:
        generated = generator.generate(question_text)
    except GenerationError as exc:
        raise _generation_http_exception(exc) from exc

    return GenerationResponse(
        answer=generated.answer,
        limitations=generated.limitations,
        external_sources_consulted=False,
    )


def create_app(
    settings: Settings | None = None, generator: Generator | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configured_settings = settings or Settings()
        engine, session_factory = create_database(configured_settings)

        owned_generator: GeminiGenerator | None = None
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            app.state.session_factory = session_factory

            if generator is not None:
                configured_generator = generator
            else:
                if configured_settings.gemini_api_key is None:
                    raise RuntimeError(
                        "EVIDENCEOPS_GEMINI_API_KEY is required for generation"
                    )

                owned_generator = GeminiGenerator(
                    api_key=configured_settings.gemini_api_key.get_secret_value(),
                    model=configured_settings.gemini_model,
                    max_output_tokens=configured_settings.gemini_max_output_tokens,
                    timeout_seconds=configured_settings.gemini_timeout_seconds,
                )
                configured_generator = owned_generator
            app.state.generator = configured_generator
            yield
        finally:
            try:
                if owned_generator is not None:
                    owned_generator.close()
            finally:
                engine.dispose()

    application = FastAPI(lifespan=lifespan)
    application.include_router(router)

    return application


app = create_app()

import logging
from time import perf_counter

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from evidenceops.config import Settings
from evidenceops.database import create_database, get_session
from evidenceops.generator_factory import create_generator
from evidenceops.generation import (
    GenerationError,
    GenerationErrorCause,
    Generator,
)
from evidenceops.models import Question
from evidenceops.metrics import GenerationMetrics
from evidenceops.observability import CorrelatedFastAPI, configure_logging
from evidenceops.schemas import (
    GenerationResponse,
    HealthCheckResponse,
    QuestionCreate,
    QuestionResponse,
)
from evidenceops.tracing import configure_tracing, finish_error, finish_success, tracer


logger = logging.getLogger(__name__)


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


def get_metrics(request: Request) -> GenerationMetrics:
    return cast(GenerationMetrics, request.app.state.metrics)


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


@router.get("/metrics")
def metrics_endpoint(metrics: GenerationMetrics = Depends(get_metrics)) -> Response:
    return Response(content=metrics.render(), media_type=CONTENT_TYPE_LATEST)


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
    metrics: GenerationMetrics = Depends(get_metrics),
) -> GenerationResponse:
    with tracer.start_as_current_span(
        "generation", record_exception=False, set_status_on_exception=False
    ) as span:
        started = perf_counter()
        logger.info("generation.started")
        try:
            generated = generator.generate(question_text)
        except GenerationError as exc:
            duration_seconds = perf_counter() - started
            finish_error(span, exc.cause.value)
            metrics.record_generation("error", duration_seconds, exc.cause)
            logger.warning("generation.failed", extra={
                "duration_ms": duration_seconds * 1000,
                "outcome": "error", "cause": exc.cause.value,
            })
            raise _generation_http_exception(exc) from exc
        except Exception:
            duration_seconds = perf_counter() - started
            finish_error(span, "unexpected_application_error")
            metrics.record_unexpected_error(duration_seconds)
            logger.error("generation.failed", extra={
                "duration_ms": duration_seconds * 1000,
                "outcome": "error", "cause": "unexpected_application_error",
            })
            raise
        duration_seconds = perf_counter() - started
        finish_success(span)
        metrics.record_generation("success", duration_seconds)
        logger.info("generation.succeeded", extra={
            "duration_ms": duration_seconds * 1000,
            "outcome": "success",
        })

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
        configure_logging()
        configured_settings = settings or Settings()
        configure_tracing(configured_settings.trace_console)
        engine, session_factory = create_database(configured_settings)

        owned_generator = None
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            app.state.session_factory = session_factory

            if generator is not None:
                configured_generator = generator
            else:
                owned_generator = create_generator(configured_settings, app.state.metrics)
                configured_generator = owned_generator
            app.state.generator = configured_generator
            yield
        finally:
            try:
                if owned_generator is not None:
                    owned_generator.close()
            finally:
                engine.dispose()

    application = CorrelatedFastAPI(lifespan=lifespan)
    application.state.metrics = GenerationMetrics()
    application.include_router(router)

    return application


app = create_app()

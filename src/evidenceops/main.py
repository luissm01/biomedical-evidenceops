import logging
from functools import partial
from time import perf_counter

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST
from sqlalchemy import Engine, text
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm import Session, sessionmaker

from evidenceops import jobs
from evidenceops.config import JobSettings, Settings
from evidenceops.database import create_database, get_session
from evidenceops.generator_factory import create_generator
from evidenceops.generation import (
    GenerationError,
    GenerationErrorCause,
    Generator,
)
from evidenceops.embeddings import LocalMedCPT, MedCPTEncoder
from evidenceops.health import check_readiness, expected_migration_heads
from evidenceops.security import (
    ApiKeyAuth, TokenBucketLimiter, enforce_llm_rate_limit, require_api_key,
)
from evidenceops.rag import RagService
from evidenceops.rag_errors import InvalidCitationsError, RagRetrievalError
from evidenceops.retrieval import search
from evidenceops.reranking import LocalMedCPTReranker, MedCPTReranker
from evidenceops.models import Question
from evidenceops.metrics import GenerationMetrics
from evidenceops.observability import CorrelatedFastAPI, configure_logging
from evidenceops.observability import job_id as job_id_context
from evidenceops.schemas import (
    GenerationResponse,
    RagRequest,
    RagHTTPResponse,
    HealthCheckResponse,
    ReadinessResponse,
    IngestionJobAccepted,
    IngestionJobCreate,
    IngestionJobResponse,
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
    GenerationErrorCause.DEADLINE_EXCEEDED: (
        504,
        "generation_deadline_exceeded",
        "Generation exceeded its total time limit",
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


def get_rag_service(request: Request) -> RagService:
    return cast(RagService, request.app.state.rag_service)


@router.post("/rag", response_model=RagHTTPResponse,
             dependencies=[Depends(enforce_llm_rate_limit)])
def generate_rag(
    body: RagRequest, service: RagService = Depends(get_rag_service),
) -> RagHTTPResponse:
    try:
        result = service.generate(body.query, published_from=body.published_from)
    except RagRetrievalError as exc:
        raise HTTPException(status_code=503, detail={
            "code": exc.cause, "message": "Evidence retrieval is unavailable",
        }) from exc
    except InvalidCitationsError as exc:
        raise HTTPException(status_code=502, detail={
            "code": "invalid_citations", "message": "Generation returned invalid citations",
        }) from exc
    except GenerationError as exc:
        raise _generation_http_exception(exc) from exc
    return RagHTTPResponse(
        answer=result.answer, limitations=result.limitations, sources=list(result.sources),
    )


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
    """Liveness: no dependency checks by design (see evidenceops.health)."""
    return HealthCheckResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse,
            responses={503: {"model": ReadinessResponse}})
def readiness_check(request: Request, response: Response) -> ReadinessResponse:
    checks = check_readiness(cast(Engine, request.app.state.engine),
                             cast(frozenset[str], request.app.state.migration_heads))
    ready = all(state == "ok" for state in checks.values())
    if not ready:
        response.status_code = 503
    return ReadinessResponse(status="ready" if ready else "not_ready", checks=checks)


@router.get("/metrics")
def metrics_endpoint(metrics: GenerationMetrics = Depends(get_metrics)) -> Response:
    return Response(content=metrics.render(), media_type=CONTENT_TYPE_LATEST)


@router.post("/ingestion-jobs", response_model=IngestionJobAccepted, status_code=202,
             dependencies=[Depends(require_api_key)])
def enqueue_ingestion_job(
    body: IngestionJobCreate,
    request: Request,
    response: Response,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=128),
    ] = None,
    metrics: GenerationMetrics = Depends(get_metrics),
) -> IngestionJobAccepted:
    """Accept a PubMed ingestion for the worker; never calls PubMed here.

    A repeated Idempotency-Key with the same parameters replays the original
    acceptance (same job, 202) instead of creating a second job.
    """
    session_factory = cast(sessionmaker[Session], request.app.state.session_factory)
    settings = cast(JobSettings, request.app.state.job_settings)
    try:
        enqueued = jobs.enqueue_ingestion(
            session_factory, query=body.query, limit=body.limit,
            max_attempts=settings.max_attempts, idempotency_key=idempotency_key,
        )
    except jobs.IdempotencyConflictError as exc:
        metrics.ingestion_jobs_enqueued.labels(outcome="conflict").inc()
        raise HTTPException(status_code=409, detail={
            "code": "idempotency_key_conflict",
            "message": "Idempotency-Key was already used with different parameters",
        }) from exc
    outcome = "created" if enqueued.created else "existing"
    metrics.ingestion_jobs_enqueued.labels(outcome=outcome).inc()
    token = job_id_context.set(str(enqueued.job_id))
    try:
        logger.info("job.enqueued", extra={"outcome": outcome})
    finally:
        job_id_context.reset(token)
    job = jobs.get_job(session_factory, enqueued.job_id)
    response.headers["Location"] = f"/ingestion-jobs/{enqueued.job_id}"
    return IngestionJobAccepted(job_id=enqueued.job_id, status=job.status)


@router.get("/ingestion-jobs/{job_id}", response_model=IngestionJobResponse)
def get_ingestion_job(job_id: UUID, request: Request) -> IngestionJobResponse:
    session_factory = cast(sessionmaker[Session], request.app.state.session_factory)
    job = jobs.get_job(session_factory, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return IngestionJobResponse(
        job_id=job.id, status=job.status, query=job.query, limit=job.search_limit,
        attempts=job.attempts, max_attempts=job.max_attempts, last_error=job.last_error,
        next_attempt_at=job.run_after if job.status == jobs.JobStatus.QUEUED else None,
        created_at=job.created_at, updated_at=job.updated_at, started_at=job.started_at,
        finished_at=job.finished_at, result=job.result,
    )


@router.post("/questions", response_model=QuestionResponse, status_code=201,
             dependencies=[Depends(require_api_key)])
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
    # Route dependencies run first: auth and rate limit before any DB/LLM work.
    dependencies=[Depends(enforce_llm_rate_limit)],
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


def _database_unavailable(request: Request, _exc: Exception) -> JSONResponse:
    """PostgreSQL unreachable, connection lost or statement/pool timeout after startup.

    Same {code, message} shape as the other typed errors; the driver message
    (host, port, SQL) is never returned or logged. Integrity or programming
    errors are bugs and keep producing a 500.
    """
    cast(GenerationMetrics, request.app.state.metrics).database_unavailable.inc()
    logger.warning("database.unavailable", extra={"cause": "database_unavailable"})
    return JSONResponse(status_code=503, content={"detail": {
        "code": "database_unavailable", "message": "Database is temporarily unavailable",
    }})


def create_app(
    settings: Settings | None = None, generator: Generator | None = None,
    encoder: MedCPTEncoder | None = None,
    reranker: MedCPTReranker | None = None,
    job_settings: JobSettings | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        configured_settings = settings or Settings()
        configure_tracing(configured_settings.trace_console)
        # Fail fast: costly and mutating endpoints must never run unprotected.
        app.state.api_key_auth = ApiKeyAuth(configured_settings.api_keys)
        app.state.rate_limiter = TokenBucketLimiter(
            configured_settings.rate_limit_capacity,
            configured_settings.rate_limit_refill_per_second,
        )
        app.state.migration_heads = expected_migration_heads()
        engine, session_factory = create_database(configured_settings)
        app.state.engine = engine

        owned_generator = None
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            app.state.session_factory = session_factory
            app.state.job_settings = job_settings or JobSettings()

            if generator is not None:
                configured_generator = generator
            else:
                owned_generator = create_generator(configured_settings, app.state.metrics)
                configured_generator = owned_generator
            app.state.generator = configured_generator
            app.state.rag_service = RagService(
                partial(search, session_factory, encoder if encoder is not None else LocalMedCPT(),
                        mode=configured_settings.retrieval_mode,
                        reranker=(reranker if reranker is not None else LocalMedCPTReranker())
                        if configured_settings.retrieval_mode == "reranking" else None),
                configured_generator, app.state.metrics,
            )
            yield
        finally:
            try:
                if owned_generator is not None:
                    owned_generator.close()
            finally:
                engine.dispose()

    application = CorrelatedFastAPI(lifespan=lifespan)
    application.state.metrics = GenerationMetrics()
    for error_type in (OperationalError, InterfaceError, PoolTimeoutError):
        application.add_exception_handler(error_type, _database_unavailable)
    application.include_router(router)

    return application


app = create_app()

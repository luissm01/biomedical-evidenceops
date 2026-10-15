"""Observe RAG operations without recording query, evidence or provider output."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import logging
from time import perf_counter

from evidenceops.generation import GenerationError
from evidenceops.metrics import GenerationMetrics
from evidenceops.rag_errors import InvalidCitationsError, RagRetrievalError
from evidenceops.tracing import finish_error, finish_success, tracer

logger = logging.getLogger(__name__)


@dataclass
class RagObservation:
    outcome: str = "success"


@contextmanager
def observe_rag(
    stage: str, metrics: GenerationMetrics | None,
) -> Iterator[RagObservation]:
    with tracer.start_as_current_span(
        f"rag.{stage}" if stage != "operation" else "rag",
        record_exception=False, set_status_on_exception=False,
    ) as span:
        observation = RagObservation()
        cause = None
        diagnostic = {}
        started = perf_counter()
        logger.info("rag.started", extra={"stage": stage})
        try:
            yield observation
        except Exception as exc:
            observation.outcome = "error"
            # Only stable application causes; never serialize exception messages.
            if isinstance(exc, GenerationError):
                cause = "invalid_citations" if isinstance(exc, InvalidCitationsError) else exc.cause.value
            elif isinstance(exc, RagRetrievalError):
                cause = exc.cause
            else:
                cause = "unexpected_application_error"
            if isinstance(exc, InvalidCitationsError):
                diagnostic = exc.diagnostic()
                for key, value in diagnostic.items():
                    span.set_attribute(f"evidenceops.{key}", value)
            finish_error(span, cause)
            raise
        finally:
            duration = perf_counter() - started
            if observation.outcome != "error":
                finish_success(span)
                span.set_attribute("evidenceops.outcome", observation.outcome)
            if metrics is not None:
                metrics.record_rag(stage, observation.outcome, duration, cause)
            logger.log(
                logging.WARNING if cause else logging.INFO,
                "rag.finished", extra={
                    "stage": stage, "outcome": observation.outcome,
                    "duration_ms": duration * 1000, "cause": cause,
                    **diagnostic,
                },
            )

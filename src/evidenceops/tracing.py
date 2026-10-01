"""Minimal, content-safe OpenTelemetry spans for API generations."""

import sys
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode

from evidenceops.generation import GenerationError, GeneratedContent


provider = TracerProvider(resource=Resource({SERVICE_NAME: "evidenceops"}))
tracer = provider.get_tracer("evidenceops")
_console_enabled = False


def configure_tracing(console: bool) -> None:
    """Enable local trace output once per process when explicitly requested."""
    global _console_enabled
    if console and not _console_enabled:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stderr)))
        _console_enabled = True


def finish_error(span: Span, cause: str) -> None:
    """Record a stable exception instead of possibly sensitive SDK exception text."""
    span.set_attribute("evidenceops.outcome", "error")
    span.set_attribute("evidenceops.error_cause", cause)
    span.record_exception(RuntimeError(cause))
    span.set_status(Status(StatusCode.ERROR))


def finish_success(span: Span) -> None:
    span.set_attribute("evidenceops.outcome", "success")
    span.set_status(Status(StatusCode.OK))


P = ParamSpec("P")
T = TypeVar("T", bound=GeneratedContent)


def traced_provider(name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Trace one adapter invocation, including SDK wait and output validation."""
    def decorate(generate: Callable[P, T]) -> Callable[P, T]:
        @wraps(generate)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            model = getattr(args[0], "_model")
            with tracer.start_as_current_span(
                f"llm.{name}",
                attributes={"evidenceops.provider": name, "evidenceops.model": model},
                record_exception=False,
                set_status_on_exception=False,
            ) as span:
                try:
                    result = generate(*args, **kwargs)
                except GenerationError as exc:
                    finish_error(span, exc.cause.value)
                    raise
                except Exception:
                    finish_error(span, "unexpected_application_error")
                    raise
                finish_success(span)
                return result
        return wrapped
    return decorate

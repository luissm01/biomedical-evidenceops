"""Safe application events and HTTP correlation, without business-contract changes."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from evidenceops.tracing import finish_error, finish_success, tracer

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": request_id.get(),
        }
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            event["trace_id"] = format(context.trace_id, "032x")
            event["span_id"] = format(context.span_id, "016x")
        # Only explicitly selected operational metadata; never exception text/stack.
        for field in ("duration_ms", "outcome", "cause", "provider", "model",
                      "source", "run_id", "requested", "unique", "batches",
                      "updated", "omitted", "failed", "unidentified_invalid"):
            if hasattr(record, field):
                event[field] = getattr(record, field)
        if hasattr(record, "created_count"):
            event["created"] = record.created_count
        return json.dumps(event, ensure_ascii=False, allow_nan=False)


def configure_logging() -> None:
    """Configure only our namespace, once; leave third-party/root handlers alone."""
    logger = logging.getLogger("evidenceops")
    if not any(getattr(handler, "_evidenceops_json", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler._evidenceops_json = True
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        identifier = str(uuid4())
        token = request_id.set(identifier)
        parts = scope.get("path", "").split("/")
        is_generation = (
            scope.get("method") == "POST"
            and len(parts) == 4
            and parts[1] == "questions"
            and parts[3] == "generate"
        )
        status_code = None

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [(k, v) for k, v in message.get("headers", [])
                           if k.lower() != b"x-request-id"]
                message = {**message, "headers": [*headers, (b"x-request-id", identifier.encode())]}
            await send(message)

        try:
            if is_generation:
                with tracer.start_as_current_span(
                    "POST /questions/{question_id}/generate",
                    kind=SpanKind.SERVER,
                    attributes={"http.request.method": "POST", "http.route": "/questions/{question_id}/generate"},
                    record_exception=False,
                    set_status_on_exception=False,
                ) as span:
                    try:
                        await self.app(scope, receive, send_with_id)
                    except Exception:
                        finish_error(span, "unexpected_application_error")
                        raise
                    if status_code is not None and status_code >= 400:
                        finish_error(span, "http_error")
                    else:
                        finish_success(span)
            else:
                await self.app(scope, receive, send_with_id)
        finally:
            request_id.reset(token)


class CorrelatedFastAPI(FastAPI):
    def build_middleware_stack(self) -> ASGIApp:
        # Outside ServerErrorMiddleware so even its unchanged 500 has the ID.
        return RequestContextMiddleware(super().build_middleware_stack())

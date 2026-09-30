"""Safe application events and HTTP correlation, without business-contract changes."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": request_id.get(),
        }
        # Only explicitly selected operational metadata; never exception text/stack.
        for field in ("duration_ms", "outcome", "cause", "model"):
            if hasattr(record, field):
                event[field] = getattr(record, field)
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

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", [])
                           if k.lower() != b"x-request-id"]
                message = {**message, "headers": [*headers, (b"x-request-id", identifier.encode())]}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id.reset(token)


class CorrelatedFastAPI(FastAPI):
    def build_middleware_stack(self) -> ASGIApp:
        # Outside ServerErrorMiddleware so even its unchanged 500 has the ID.
        return RequestContextMiddleware(super().build_middleware_stack())

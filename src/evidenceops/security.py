"""API key authentication and per-key rate limiting for costly endpoints (D037).

Deliberately small: static keys from configuration, no users or roles.
Keys are compared in constant time and never logged, echoed or used as labels;
callers are identified by an opaque index ("key-0", "key-1"…).
"""

import hmac
import logging
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from fastapi import Depends, HTTPException, Request
from pydantic import SecretStr

from evidenceops.metrics import GenerationMetrics

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"
_MAX_KEY_LENGTH = 256


class ApiKeyAuth:
    def __init__(self, keys: tuple[SecretStr, ...]) -> None:
        if not keys:
            raise RuntimeError("EVIDENCEOPS_API_KEYS is required to protect write and LLM endpoints")
        self._keys = [key.get_secret_value().encode() for key in keys]

    def identify(self, presented: str | None) -> str | None:
        """Return an opaque key id, or None. Time does not depend on which byte differs.

        Every configured key is compared (no early exit), so timing does not
        reveal which key, or how much of it, matched.
        """
        if not presented or len(presented) > _MAX_KEY_LENGTH:
            return None
        candidate = presented.encode()
        matches = [hmac.compare_digest(candidate, key) for key in self._keys]
        return f"key-{matches.index(True)}" if any(matches) else None


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated: float


class TokenBucketLimiter:
    """In-memory token bucket per caller: ``capacity`` burst, steady ``refill`` per second.

    State lives in this process only: with N API instances a caller can get up
    to N times the configured rate. A shared store would be required for a
    global limit (out of scope, D037).
    """

    def __init__(self, capacity: int, refill_per_second: float,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._capacity = capacity
        self._refill = refill_per_second
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()  # sync endpoints run in a thread pool

    def acquire(self, caller: str) -> float | None:
        """Take one token; return None if allowed, else seconds until one is available."""
        with self._lock:
            now = self._clock()
            bucket = self._buckets.setdefault(caller, _Bucket(self._capacity, now))
            elapsed = max(0.0, now - bucket.updated)
            bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill)
            bucket.updated = now
            if bucket.tokens >= 1:
                bucket.tokens -= 1
                return None
            return (1 - bucket.tokens) / self._refill


def _reject(request: Request, status_code: int, code: str, message: str,
            headers: dict[str, str] | None = None) -> HTTPException:
    metrics = cast(GenerationMetrics, request.app.state.metrics)
    metrics.api_rejections.labels(reason=code).inc()
    logger.warning("api.request_rejected", extra={"cause": code})
    return HTTPException(status_code=status_code, detail={"code": code, "message": message},
                         headers=headers)


def require_api_key(request: Request) -> str:
    """Dependency for endpoints that mutate data or cost LLM calls.

    The header is read directly (not as a validated parameter) so a malformed
    key can never be echoed back inside a 422 validation error.
    """
    auth = cast(ApiKeyAuth, request.app.state.api_key_auth)
    caller = auth.identify(request.headers.get(API_KEY_HEADER))
    if caller is None:
        raise _reject(request, 401, "unauthorized", "A valid API key is required",
                      headers={"WWW-Authenticate": "ApiKey"})
    return caller


def enforce_llm_rate_limit(request: Request, caller: str = Depends(require_api_key)) -> None:
    limiter = cast(TokenBucketLimiter, request.app.state.rate_limiter)
    wait = limiter.acquire(caller)
    if wait is not None:
        raise _reject(request, 429, "rate_limited", "Too many requests for this API key",
                      headers={"Retry-After": str(max(1, math.ceil(wait)))})

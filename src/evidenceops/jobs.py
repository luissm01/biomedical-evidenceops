"""PostgreSQL-backed job queue for asynchronous PubMed ingestion (D036).

Every queue operation is one short transaction. The claim commits immediately:
the row lock only arbitrates *who* takes a job, and the lease (a timestamp)
guards ownership while it runs, so no connection or lock is held during the
PubMed calls. All times come from PostgreSQL's ``now()``, never worker clocks.

``attempts`` doubles as a fencing token: each claim increments it, and every
completion is conditioned on ``status = 'running' AND attempts = :attempt``.
A worker whose lease expired and whose job was reclaimed therefore cannot
overwrite the newer attempt's outcome.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from evidenceops.models import IngestionJob
from evidenceops.pubmed import PubMedError, PubMedErrorCause


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


LEASE_EXPIRED = "lease_expired"
RELEASED = "released_on_shutdown"


class IdempotencyConflictError(Exception):
    """The idempotency key already identifies a job with other parameters."""


@dataclass(frozen=True, slots=True)
class EnqueueResult:
    job_id: UUID
    created: bool


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    id: UUID
    query: str
    search_limit: int
    attempt: int
    max_attempts: int
    recovered: bool  # True when taken over from an expired lease


def enqueue_ingestion(
    session_factory: sessionmaker[Session],
    *,
    query: str,
    limit: int,
    max_attempts: int,
    idempotency_key: str | None = None,
) -> EnqueueResult:
    """Insert a queued job, or return the job already bound to the key.

    ``ON CONFLICT DO NOTHING`` waits for a concurrent insert of the same key to
    commit, so the follow-up SELECT always sees the winning row.
    """
    job_id = uuid4()
    with session_factory.begin() as session:
        inserted = session.execute(text("""
            INSERT INTO ingestion_jobs (id, status, query, search_limit, idempotency_key, max_attempts)
            VALUES (:id, 'queued', :query, :limit, :key, :max_attempts)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
        """), {"id": job_id, "query": query, "limit": limit, "key": idempotency_key,
               "max_attempts": max_attempts}).scalar_one_or_none()
        if inserted is not None:
            return EnqueueResult(inserted, created=True)
        existing = session.execute(
            select(IngestionJob).where(IngestionJob.idempotency_key == idempotency_key)
        ).scalar_one()
        if (existing.query, existing.search_limit) != (query, limit):
            raise IdempotencyConflictError(idempotency_key)
        return EnqueueResult(existing.id, created=False)


def get_job(session_factory: sessionmaker[Session], job_id: UUID) -> IngestionJob | None:
    with session_factory() as session:
        return session.get(IngestionJob, job_id)


def fail_exhausted_leases(session_factory: sessionmaker[Session]) -> list[UUID]:
    """Fail running jobs whose lease expired with no attempts left.

    A worker that died on its last attempt must not leave the job running
    forever; it cannot be reclaimed, so it becomes terminal here.
    """
    with session_factory.begin() as session:
        return list(session.execute(text("""
            UPDATE ingestion_jobs
            SET status = 'failed', last_error = :error, lease_expires_at = NULL,
                finished_at = now(), updated_at = now()
            WHERE status = 'running' AND lease_expires_at <= now() AND attempts >= max_attempts
            RETURNING id
        """), {"error": LEASE_EXPIRED}).scalars())


def claim_next(
    session_factory: sessionmaker[Session], *, worker_id: str, lease_seconds: float,
) -> ClaimedJob | None:
    """Atomically take one due job: queued, or running with an expired lease.

    ``FOR UPDATE SKIP LOCKED`` makes concurrent workers skip rows another
    transaction is claiming instead of waiting or taking the same row.
    """
    with session_factory.begin() as session:
        row = session.execute(text("""
            WITH candidate AS (
                SELECT id, status AS previous_status
                FROM ingestion_jobs
                WHERE (status = 'queued' AND run_after <= now())
                   OR (status = 'running' AND lease_expires_at <= now() AND attempts < max_attempts)
                ORDER BY run_after, created_at
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE ingestion_jobs AS job
            SET status = 'running',
                attempts = job.attempts + 1,
                worker_id = :worker_id,
                lease_expires_at = now() + make_interval(secs => :lease_seconds),
                started_at = now(),
                updated_at = now(),
                last_error = CASE WHEN candidate.previous_status = 'running'
                                  THEN :lease_expired ELSE job.last_error END
            FROM candidate
            WHERE job.id = candidate.id
            RETURNING job.id, job.query, job.search_limit, job.attempts, job.max_attempts,
                      candidate.previous_status
        """), {"worker_id": worker_id, "lease_seconds": lease_seconds,
               "lease_expired": LEASE_EXPIRED}).one_or_none()
    if row is None:
        return None
    return ClaimedJob(row.id, row.query, row.search_limit, row.attempts, row.max_attempts,
                      recovered=row.previous_status == JobStatus.RUNNING)


_FENCE = "WHERE id = :id AND status = 'running' AND attempts = :attempt"


def _finish(session_factory: sessionmaker[Session], job: ClaimedJob, assignments: str,
            parameters: dict) -> bool:
    """Apply a fenced transition; False means this attempt lost ownership."""
    with session_factory.begin() as session:
        result = session.execute(text(f"""
            UPDATE ingestion_jobs
            SET {assignments}, lease_expires_at = NULL, updated_at = now()
            {_FENCE}
        """), {"id": job.id, "attempt": job.attempt, **parameters})
        return result.rowcount == 1


def mark_succeeded(session_factory: sessionmaker[Session], job: ClaimedJob, result: dict) -> bool:
    return _finish(session_factory, job,
                   "status = 'succeeded', result = CAST(:result AS jsonb), finished_at = now()",
                   {"result": _json(result)})


def mark_failed(session_factory: sessionmaker[Session], job: ClaimedJob, *, error: str) -> bool:
    return _finish(session_factory, job,
                   "status = 'failed', last_error = :error, finished_at = now()", {"error": error})


def schedule_retry(
    session_factory: sessionmaker[Session], job: ClaimedJob, *, error: str, delay_seconds: float,
) -> bool:
    return _finish(session_factory, job,
                   "status = 'queued', last_error = :error, worker_id = NULL, "
                   "run_after = now() + make_interval(secs => :delay)",
                   {"error": error, "delay": delay_seconds})


def release(session_factory: sessionmaker[Session], job: ClaimedJob) -> bool:
    """Return an interrupted job to the queue immediately (forced shutdown)."""
    return _finish(session_factory, job,
                   "status = 'queued', last_error = :error, worker_id = NULL, run_after = now()",
                   {"error": RELEASED})


def count_by_status(session_factory: sessionmaker[Session]) -> dict[str, int]:
    with session_factory() as session:
        rows = session.execute(text(
            "SELECT status, count(*) FROM ingestion_jobs GROUP BY status"
        )).all()
    counts = {status.value: 0 for status in JobStatus}
    counts.update({status: count for status, count in rows})
    return counts


def backoff_seconds(attempt: int, *, base: float, maximum: float) -> float:
    """Exponential backoff after the given failed attempt: base, 2·base, 4·base…"""
    return min(base * 2 ** (attempt - 1), maximum)


_RETRYABLE_CAUSES = {PubMedErrorCause.TIMEOUT, PubMedErrorCause.TRANSPORT,
                     PubMedErrorCause.RATE_LIMIT}


def is_retryable(error: PubMedError) -> bool:
    """Network failures, NCBI 429 and 5xx are transient; 4xx and bad XML are not."""
    if error.cause in _RETRYABLE_CAUSES:
        return True
    return (error.cause == PubMedErrorCause.HTTP_ERROR
            and error.status_code is not None and error.status_code >= 500)


def error_code(operation: str, error: PubMedError) -> str:
    """Stable, content-free code such as ``search_timeout`` or ``fetch_http_error_503``."""
    code = f"{operation}_{error.cause.value}"
    if error.cause == PubMedErrorCause.HTTP_ERROR and error.status_code is not None:
        code += f"_{error.status_code}"
    return code


def _json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)

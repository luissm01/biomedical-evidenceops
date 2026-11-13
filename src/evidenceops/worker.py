"""Synchronous polling worker for queued PubMed ingestion jobs (D036).

One job at a time per process; scale out by starting more processes. Delivery
is at-least-once: a job may run again after a crash or lost lease, which is
safe because the pipeline upserts each publication by its PubMed identity.
"""

import logging
import os
import socket
import threading
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from evidenceops import jobs
from evidenceops.config import JobSettings
from evidenceops.ingestion import ingest_pubmed
from evidenceops.metrics import JobMetrics
from evidenceops.observability import job_id as job_id_context
from evidenceops.pubmed import PubMedClient, PubMedError, PubMedFetchResult

logger = logging.getLogger(__name__)


class _ErrorRecordingClient:
    """Pass-through PubMed client that remembers adapter errors.

    The M6 pipeline turns PubMed errors into summary failures (D023) so the
    synchronous CLI can report partial results. The worker needs the original
    error to decide between retry and permanent failure, without changing that
    pipeline or its summary contract.
    """

    def __init__(self, client: PubMedClient) -> None:
        self._client = client
        self.errors: list[tuple[str, PubMedError]] = []

    def search(self, query: str, *, limit: int) -> list[str]:
        try:
            return self._client.search(query, limit=limit)
        except PubMedError as exc:
            self.errors.append(("search", exc))
            raise

    def fetch(self, pmids: list[str]) -> PubMedFetchResult:
        try:
            return self._client.fetch(pmids)
        except PubMedError as exc:
            self.errors.append(("fetch", exc))
            raise


@dataclass(frozen=True, slots=True)
class AttemptOutcome:
    status: str  # succeeded | retry | failed
    error: str | None = None
    result: dict | None = None


def run_ingestion_attempt(
    job: jobs.ClaimedJob, client: PubMedClient, session_factory: sessionmaker[Session],
) -> AttemptOutcome:
    """Run the existing pipeline once and classify its outcome.

    Retry when any PubMed call failed transiently: the whole job is repeated,
    which is safe thanks to the idempotent upsert. A permanent PubMed error
    fails the job. Record-level problems (invalid records, a document's
    persistence error) are data outcomes reported in the result, not job errors.
    """
    recorder = _ErrorRecordingClient(client)
    try:
        summary = ingest_pubmed(recorder, session_factory, query=job.query, limit=job.search_limit)
    except Exception:
        return AttemptOutcome("failed", error="unexpected_application_error")
    transient = [(op, exc) for op, exc in recorder.errors if jobs.is_retryable(exc)]
    if transient:
        return AttemptOutcome("retry", error=jobs.error_code(*transient[0]))
    if recorder.errors:
        return AttemptOutcome("failed", error=jobs.error_code(*recorder.errors[0]))
    return AttemptOutcome("succeeded", result=summary.as_dict())


def default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"


class IngestionWorker:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        client: PubMedClient,
        settings: JobSettings,
        *,
        worker_id: str | None = None,
        metrics: JobMetrics | None = None,
        stop: threading.Event | None = None,
        attempt: Callable[..., AttemptOutcome] = run_ingestion_attempt,
    ) -> None:
        self.session_factory = session_factory
        self.client = client
        self.settings = settings
        self.worker_id = worker_id or default_worker_id()
        self.metrics = metrics or JobMetrics()
        self.stop = stop or threading.Event()
        self._attempt = attempt

    def run(self) -> None:
        """Poll until asked to stop; a stop request lets the current job finish.

        Consecutive polling failures (database down, statement timeout) wait
        ``poll_seconds · 2^(n-1)`` up to ``poll_backoff_max_seconds``, so a
        fleet of workers does not hammer a recovering database. The first
        successful poll resets the wait.
        """
        logger.info("worker.started", extra={"worker_id": self.worker_id})
        failures = 0
        try:
            while not self.stop.is_set():
                try:
                    processed = self.run_once()
                except SQLAlchemyError:
                    failures += 1
                    delay = min(self.settings.poll_seconds * 2 ** (failures - 1),
                                self.settings.poll_backoff_max_seconds)
                    logger.warning("worker.poll_failed", extra={
                        "worker_id": self.worker_id, "cause": "database_error",
                        "attempt": failures, "delay_seconds": delay,
                    })
                    self.stop.wait(delay)
                    continue
                if failures:
                    logger.info("worker.poll_recovered", extra={
                        "worker_id": self.worker_id, "attempt": failures,
                    })
                    failures = 0
                if not processed:
                    self.stop.wait(self.settings.poll_seconds)
        finally:
            logger.info("worker.stopped", extra={"worker_id": self.worker_id})

    def run_once(self) -> bool:
        """Fail exhausted leases, then claim and process at most one job."""
        exhausted = jobs.fail_exhausted_leases(self.session_factory)
        for failed_id in exhausted:
            self.metrics.lease_expirations.labels(action="failed").inc()
            token = job_id_context.set(str(failed_id))
            try:
                logger.warning("job.failed", extra={
                    "worker_id": self.worker_id, "outcome": "failed", "cause": jobs.LEASE_EXPIRED,
                })
            finally:
                job_id_context.reset(token)
        job = jobs.claim_next(self.session_factory, worker_id=self.worker_id,
                              lease_seconds=self.settings.lease_seconds)
        if job is None:
            return False
        token = job_id_context.set(str(job.id))
        try:
            self._process(job)
        finally:
            job_id_context.reset(token)
        return True

    def _process(self, job: jobs.ClaimedJob) -> None:
        context = {"worker_id": self.worker_id, "attempt": job.attempt,
                   "max_attempts": job.max_attempts}
        if job.recovered:
            self.metrics.lease_expirations.labels(action="reclaimed").inc()
        logger.info("job.claimed", extra={**context, "recovered": job.recovered})
        started = perf_counter()
        try:
            outcome = self._attempt(job, self.client, self.session_factory)
        except KeyboardInterrupt:
            # Forced shutdown (second signal): hand the job back instead of
            # waiting for the lease to expire.
            released = jobs.release(self.session_factory, job)
            self._record(job, "released" if released else "lease_lost", started, context,
                         cause=jobs.RELEASED)
            raise

        if outcome.status == "succeeded":
            label = "succeeded"
            owned = jobs.mark_succeeded(self.session_factory, job, outcome.result or {})
        elif outcome.status == "retry" and job.attempt < job.max_attempts:
            label = "retried"
            delay = jobs.backoff_seconds(job.attempt, base=self.settings.backoff_base_seconds,
                                         maximum=self.settings.backoff_max_seconds)
            context["delay_seconds"] = delay
            owned = jobs.schedule_retry(self.session_factory, job, error=outcome.error,
                                        delay_seconds=delay)
            if owned:
                self.metrics.retries.labels(cause=outcome.error).inc()
        else:  # permanent error, or transient error with no attempts left
            label = "failed"
            owned = jobs.mark_failed(self.session_factory, job, error=outcome.error)
        self._record(job, label if owned else "lease_lost", started, context, cause=outcome.error)

    def _record(self, job: jobs.ClaimedJob, outcome: str, started: float, context: dict,
                *, cause: str | None) -> None:
        duration = perf_counter() - started
        self.metrics.record_attempt(outcome, duration)
        fields = {**context, "outcome": outcome, "duration_ms": round(duration * 1000, 3)}
        if cause is not None:
            fields["cause"] = cause
        if outcome == "lease_lost":
            # Another worker owns a newer attempt; our result was discarded.
            logger.warning("job.lease_lost", extra=fields)
        elif outcome == "succeeded":
            logger.info("job.succeeded", extra=fields)
        elif outcome == "retried":
            logger.warning("job.retry_scheduled", extra=fields)
        elif outcome == "released":
            logger.warning("job.released", extra=fields)
        else:
            logger.warning("job.failed", extra=fields)

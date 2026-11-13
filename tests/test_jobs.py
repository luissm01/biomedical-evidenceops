"""PostgreSQL job queue and worker (M11.1). No real PubMed calls or inferences."""

import json
import logging
import threading
from collections import Counter
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import delete, select, text

from evidenceops import jobs
from evidenceops.config import JobSettings, PubMedSettings
from evidenceops.database import create_database
from evidenceops.metrics import JobMetrics
from evidenceops.models import IngestionJob, Publication
from evidenceops.observability import JsonFormatter
from evidenceops.pubmed import PubMedClient, PubMedError, PubMedErrorCause
from evidenceops.worker import AttemptOutcome, IngestionWorker, run_ingestion_attempt

FIXTURE = (Path(__file__).parent / "fixtures/pubmed_articles.xml").read_bytes()
SETTINGS = JobSettings(_env_file=None, max_attempts=3, backoff_base_seconds=10,
                       backoff_max_seconds=25, lease_seconds=60, poll_seconds=0.01)


def esearch(*ids: str) -> bytes:
    body = "".join(f"<Id>{pmid}</Id>" for pmid in ids)
    return f"<eSearchResult><Count>{len(ids)}</Count><IdList>{body}</IdList></eSearchResult>".encode()


@contextmanager
def pubmed(handler):
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with PubMedClient(PubMedSettings(_env_file=None), http_client=http,
                          sleep=lambda _: None) as client:
            yield client


def ok_pubmed(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("esearch.fcgi"):
        return httpx.Response(200, content=esearch("12345", "67890"))
    return httpx.Response(200, content=FIXTURE)


# --- Pure policy: no database --------------------------------------------------------


def test_backoff_is_exponential_and_capped():
    delays = [jobs.backoff_seconds(n, base=10, maximum=25) for n in (1, 2, 3, 4)]
    assert delays == [10, 20, 25, 25]


@pytest.mark.parametrize(("error", "retryable", "code"), [
    (PubMedError(PubMedErrorCause.TIMEOUT, "x"), True, "search_timeout"),
    (PubMedError(PubMedErrorCause.TRANSPORT, "x"), True, "search_transport"),
    (PubMedError(PubMedErrorCause.RATE_LIMIT, "x", status_code=429), True, "search_rate_limit"),
    (PubMedError(PubMedErrorCause.HTTP_ERROR, "x", status_code=503), True, "search_http_error_503"),
    (PubMedError(PubMedErrorCause.HTTP_ERROR, "x", status_code=400), False, "search_http_error_400"),
    (PubMedError(PubMedErrorCause.INVALID_RESPONSE, "x"), False, "search_invalid_response"),
])
def test_error_classification(error, retryable, code):
    assert jobs.is_retryable(error) is retryable
    assert jobs.error_code("search", error) == code


def test_pubmed_error_keeps_http_status():
    with pubmed(lambda _: httpx.Response(502)) as client:
        with pytest.raises(PubMedError) as raised:
            client.search("asthma", limit=1)
    assert (raised.value.cause, raised.value.status_code) == (PubMedErrorCause.HTTP_ERROR, 502)


CLAIMED = jobs.ClaimedJob(id=None, query="asthma", search_limit=2, attempt=1, max_attempts=3,
                          recovered=False)


@pytest.mark.parametrize(("response", "expected"), [
    (httpx.Response(503), AttemptOutcome("retry", error="search_http_error_503")),
    (httpx.Response(429), AttemptOutcome("retry", error="search_rate_limit")),
    (httpx.Response(404), AttemptOutcome("failed", error="search_http_error_404")),
    (httpx.Response(200, content=b"<nope/>"), AttemptOutcome("failed", error="search_invalid_response")),
])
def test_attempt_classifies_search_failures_without_touching_database(response, expected):
    with pubmed(lambda _: response) as client:
        assert run_ingestion_attempt(CLAIMED, client, session_factory=None) == expected


def test_attempt_turns_unexpected_errors_into_permanent_failure():
    def boom(_request):
        raise RuntimeError("programming error")
    with pubmed(boom) as client:
        outcome = run_ingestion_attempt(CLAIMED, client, session_factory=None)
    assert outcome == AttemptOutcome("failed", error="unexpected_application_error")


# --- Queue on PostgreSQL ----------------------------------------------------------------


@pytest.fixture
def factory(test_settings, migrated_database):
    engine, session_factory = create_database(test_settings)

    def clean():
        with session_factory.begin() as session:
            session.execute(delete(IngestionJob))
            session.execute(delete(Publication))

    clean()
    try:
        yield session_factory
    finally:
        clean()
        engine.dispose()


def enqueue(factory, query="asthma", limit=2, key=None, max_attempts=3):
    return jobs.enqueue_ingestion(factory, query=query, limit=limit, max_attempts=max_attempts,
                                  idempotency_key=key).job_id


def load(factory, job_id) -> IngestionJob:
    return jobs.get_job(factory, job_id)


def expire_lease(factory, job_id):
    with factory.begin() as session:
        session.execute(text(
            "UPDATE ingestion_jobs SET lease_expires_at = now() - interval '1 second' WHERE id = :id"
        ), {"id": job_id})


def make_due(factory, job_id):
    with factory.begin() as session:
        session.execute(text("UPDATE ingestion_jobs SET run_after = now() WHERE id = :id"),
                        {"id": job_id})


def scripted_worker(factory, outcomes, **kwargs):
    """Worker whose attempts return prefixed outcomes, in order."""
    script = iter(outcomes)
    return IngestionWorker(factory, client=None, settings=SETTINGS,
                           attempt=lambda *_: next(script), **kwargs)


def test_enqueue_creates_a_queued_job(factory):
    job = load(factory, enqueue(factory))
    assert (job.status, job.attempts, job.max_attempts, job.lease_expires_at) == ("queued", 0, 3, None)


def test_idempotency_key_returns_existing_job_and_rejects_other_parameters(factory):
    first = jobs.enqueue_ingestion(factory, query="asthma", limit=2, max_attempts=3, idempotency_key="k1")
    again = jobs.enqueue_ingestion(factory, query="asthma", limit=2, max_attempts=3, idempotency_key="k1")
    assert first.created and not again.created and first.job_id == again.job_id
    with pytest.raises(jobs.IdempotencyConflictError):
        jobs.enqueue_ingestion(factory, query="asthma", limit=5, max_attempts=3, idempotency_key="k1")
    assert enqueue(factory) != enqueue(factory)  # no key: independent jobs
    with factory() as session:
        assert session.scalar(select(text("count(*)")).select_from(IngestionJob)) == 3


def test_concurrent_enqueues_with_the_same_key_create_one_job(factory):
    barrier = threading.Barrier(8)
    results = []

    def submit():
        barrier.wait()
        results.append(jobs.enqueue_ingestion(factory, query="asthma", limit=2, max_attempts=3,
                                              idempotency_key="same"))

    threads = [threading.Thread(target=submit) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len({result.job_id for result in results}) == 1
    assert sum(result.created for result in results) == 1


def test_success_transition_records_result(factory):
    job_id = enqueue(factory)
    claimed = jobs.claim_next(factory, worker_id="w1", lease_seconds=60)
    running = load(factory, job_id)
    assert (claimed.id, claimed.attempt, claimed.recovered) == (job_id, 1, False)
    assert (running.status, running.worker_id, running.attempts) == ("running", "w1", 1)
    assert running.lease_expires_at > running.started_at
    assert jobs.claim_next(factory, worker_id="w2", lease_seconds=60) is None
    assert jobs.mark_succeeded(factory, claimed, {"created": 2})
    done = load(factory, job_id)
    assert (done.status, done.result, done.lease_expires_at) == ("succeeded", {"created": 2}, None)
    assert done.finished_at is not None


def test_retryable_error_backs_off_then_fails_after_max_attempts(factory):
    job_id = enqueue(factory)
    worker = scripted_worker(factory, [AttemptOutcome("retry", error="search_timeout")] * 3)

    assert worker.run_once()
    job = load(factory, job_id)
    assert (job.status, job.attempts, job.last_error, job.worker_id) == ("queued", 1, "search_timeout", None)
    with factory() as session:
        delay = session.scalar(text("SELECT extract(epoch FROM run_after - updated_at) "
                                    "FROM ingestion_jobs WHERE id = :id"), {"id": job_id})
    assert float(delay) == pytest.approx(10)
    assert not worker.run_once()  # not due yet: backoff is enforced by the claim

    make_due(factory, job_id)
    assert worker.run_once()
    with factory() as session:
        delay = session.scalar(text("SELECT extract(epoch FROM run_after - updated_at) "
                                    "FROM ingestion_jobs WHERE id = :id"), {"id": job_id})
    assert float(delay) == pytest.approx(20)

    make_due(factory, job_id)
    assert worker.run_once()
    job = load(factory, job_id)
    assert (job.status, job.attempts, job.last_error) == ("failed", 3, "search_timeout")
    samples = worker.metrics.render().decode()
    assert 'evidenceops_ingestion_job_attempts_total{outcome="retried"} 2.0' in samples
    assert 'evidenceops_ingestion_job_attempts_total{outcome="failed"} 1.0' in samples
    assert 'evidenceops_ingestion_job_retries_total{cause="search_timeout"} 2.0' in samples


def test_permanent_error_fails_without_retry(factory):
    job_id = enqueue(factory)
    worker = scripted_worker(factory, [AttemptOutcome("failed", error="search_http_error_400")])
    assert worker.run_once()
    job = load(factory, job_id)
    assert (job.status, job.attempts, job.last_error) == ("failed", 1, "search_http_error_400")


def test_skip_locked_never_hands_a_locked_job_to_another_worker(factory):
    first, second = enqueue(factory), enqueue(factory)
    with factory.begin() as holder:  # another worker mid-claim, holding the row lock
        locked = holder.execute(text(
            "SELECT id FROM ingestion_jobs ORDER BY run_after, created_at LIMIT 1 FOR UPDATE"
        )).scalar_one()
        assert locked == first
        claimed = jobs.claim_next(factory, worker_id="w2", lease_seconds=60)
        assert claimed.id == second
        assert jobs.claim_next(factory, worker_id="w3", lease_seconds=60) is None


def test_concurrent_workers_never_process_the_same_job(factory):
    job_ids = {enqueue(factory) for _ in range(40)}
    processed: list = []
    lock = threading.Lock()
    barrier = threading.Barrier(4)

    def attempt(job, _client, _factory):
        with lock:
            processed.append(job.id)
        return AttemptOutcome("succeeded", result={})

    def run(name):
        worker = IngestionWorker(factory, None, SETTINGS, worker_id=name, attempt=attempt)
        barrier.wait()
        while worker.run_once():
            pass

    threads = [threading.Thread(target=run, args=(f"w{i}",)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert Counter(processed).most_common(1)[0][1] == 1
    assert set(processed) == job_ids
    with factory() as session:
        statuses = session.scalars(select(IngestionJob.status)).all()
    assert set(statuses) == {"succeeded"}


def test_expired_lease_is_recovered_and_the_stale_worker_is_fenced(factory):
    job_id = enqueue(factory)
    dead = jobs.claim_next(factory, worker_id="dead", lease_seconds=60)
    assert jobs.claim_next(factory, worker_id="alive", lease_seconds=60) is None  # lease still valid

    expire_lease(factory, job_id)  # simulated crash: no heartbeat, lease runs out
    worker = scripted_worker(factory, [AttemptOutcome("succeeded", result={"created": 2})],
                             worker_id="alive")
    assert worker.run_once()
    job = load(factory, job_id)
    assert (job.status, job.attempts, job.worker_id) == ("succeeded", 2, "alive")
    assert job.last_error == jobs.LEASE_EXPIRED
    assert 'lease_expirations_total{action="reclaimed"} 1.0' in worker.metrics.render().decode()

    # The "dead" worker wakes up late: its attempt is no longer the current one.
    assert not jobs.mark_failed(factory, dead, error="search_timeout")
    assert load(factory, job_id).status == "succeeded"


def test_expired_lease_on_last_attempt_fails_the_job(factory):
    job_id = enqueue(factory, max_attempts=1)
    jobs.claim_next(factory, worker_id="dead", lease_seconds=60)
    expire_lease(factory, job_id)
    worker = scripted_worker(factory, [])
    assert not worker.run_once()
    job = load(factory, job_id)
    assert (job.status, job.last_error, job.lease_expires_at) == ("failed", jobs.LEASE_EXPIRED, None)


def test_forced_shutdown_releases_the_running_job(factory):
    job_id = enqueue(factory)

    def interrupted(*_args):
        raise KeyboardInterrupt

    worker = IngestionWorker(factory, None, SETTINGS, attempt=interrupted)
    with pytest.raises(KeyboardInterrupt):
        worker.run_once()
    job = load(factory, job_id)
    assert (job.status, job.last_error, job.lease_expires_at) == ("queued", jobs.RELEASED, None)
    assert jobs.claim_next(factory, worker_id="next", lease_seconds=60).id == job_id


def test_stop_request_lets_the_current_job_finish(factory):
    first, second = enqueue(factory), enqueue(factory)
    stop = threading.Event()

    def attempt(job, *_):
        stop.set()  # signal arrives while the first job is running
        return AttemptOutcome("succeeded", result={})

    IngestionWorker(factory, None, SETTINGS, stop=stop, attempt=attempt).run()
    assert load(factory, first).status == "succeeded"
    assert load(factory, second).status == "queued"


def test_worker_runs_the_real_pipeline_with_retry_and_correlated_logs(factory):
    job_id = enqueue(factory)
    calls = Counter()

    def flaky(request):
        calls[request.url.path] += 1
        if request.url.path.endswith("esearch.fcgi") and calls[request.url.path] == 1:
            return httpx.Response(503)
        if request.url.path.endswith("esearch.fcgi"):
            assert parse_qs(request.url.query.decode())["retmax"] == ["2"]
        return ok_pubmed(request)

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("evidenceops")
    logger.addHandler(handler)
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    try:
        with pubmed(flaky) as client:
            worker = IngestionWorker(factory, client, SETTINGS, worker_id="w1",
                                     metrics=JobMetrics(lambda: jobs.count_by_status(factory)))
            assert worker.run_once()
            assert load(factory, job_id).last_error == "search_http_error_503"
            make_due(factory, job_id)
            assert worker.run_once()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    job = load(factory, job_id)
    assert (job.status, job.attempts) == ("succeeded", 2)
    assert (job.result["created"], job.result["failed"]) == (2, 0)
    with factory() as session:
        assert session.scalar(select(text("count(*)")).select_from(Publication)) == 2

    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    in_job = [event for event in events if event["event"].startswith(("job.", "ingestion."))]
    assert {event["job_id"] for event in in_job} == {str(job_id)}
    assert [event["event"] for event in in_job] == [
        "job.claimed", "ingestion.started", "ingestion.finished", "job.retry_scheduled",
        "job.claimed", "ingestion.started", "ingestion.finished", "job.succeeded",
    ]
    assert "asthma" not in stream.getvalue()  # query content is not logged
    assert 'evidenceops_ingestion_jobs{status="succeeded"} 1.0' in worker.metrics.render().decode()


def test_redelivered_job_does_not_duplicate_publications(factory):
    """At-least-once is safe: the same ingestion twice upserts, never duplicates."""
    job_id = enqueue(factory)
    with pubmed(ok_pubmed) as client:
        first = jobs.claim_next(factory, worker_id="dead", lease_seconds=60)
        assert run_ingestion_attempt(first, client, factory).status == "succeeded"
        expire_lease(factory, job_id)  # crashed before recording success
        worker = IngestionWorker(factory, client, SETTINGS)
        assert worker.run_once()
    job = load(factory, job_id)
    assert (job.status, job.result["created"], job.result["updated"]) == ("succeeded", 0, 2)
    with factory() as session:
        assert session.scalar(select(text("count(*)")).select_from(Publication)) == 2


# --- HTTP API ------------------------------------------------------------------------


@pytest.fixture
def api(client, factory):
    return client


def test_api_enqueues_with_202_and_reports_status(api):
    response = api.post("/ingestion-jobs", json={"query": " asthma ", "limit": 5})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert response.json()["status"] == "queued"
    assert response.headers["location"] == f"/ingestion-jobs/{job_id}"

    status = api.get(f"/ingestion-jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert (body["status"], body["query"], body["limit"], body["attempts"]) == ("queued", "asthma", 5, 0)
    assert body["next_attempt_at"] is not None and body["result"] is None


def test_api_idempotency_key_replays_and_conflicts(api):
    headers = {"Idempotency-Key": "demo-1"}
    first = api.post("/ingestion-jobs", json={"query": "asthma", "limit": 5}, headers=headers)
    again = api.post("/ingestion-jobs", json={"query": "asthma", "limit": 5}, headers=headers)
    assert first.status_code == again.status_code == 202
    assert first.json()["job_id"] == again.json()["job_id"]
    conflict = api.post("/ingestion-jobs", json={"query": "copd", "limit": 5}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_key_conflict"
    metrics = api.get("/metrics").text
    assert 'evidenceops_ingestion_jobs_enqueued_total{outcome="created"} 1.0' in metrics
    assert 'evidenceops_ingestion_jobs_enqueued_total{outcome="existing"} 1.0' in metrics


@pytest.mark.parametrize("body", [
    {"query": "asthma", "limit": 0}, {"query": "asthma", "limit": 101},
    {"query": "   ", "limit": 5}, {"query": "asthma"}, {"query": "asthma", "limit": "5"},
    {"query": "asthma", "limit": 5, "pmids": ["1"]},
])
def test_api_rejects_invalid_requests(api, body):
    assert api.post("/ingestion-jobs", json=body).status_code == 422


def test_api_unknown_job_is_404(api):
    assert api.get("/ingestion-jobs/00000000-0000-0000-0000-000000000000").status_code == 404

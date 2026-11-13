"""M11.2: health/readiness, database outages, LLM deadline, auth, rate limiting, secrets.

A toggleable TCP proxy in front of the test PostgreSQL simulates an outage:
"down" drops every open connection and refuses new sessions, "up" restores
forwarding. No network beyond localhost, no PubMed, no LLM inferences.
"""

import io
import json
import logging
import socket
import threading
import time
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine import make_url

from conftest import AUTH_HEADERS, TEST_API_KEY, FakeGenerator
from evidenceops.config import JobSettings, Settings
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause
from evidenceops.generator_factory import DeadlineGenerator
from evidenceops.main import create_app
from evidenceops.observability import JsonFormatter, request_id
from evidenceops.security import ApiKeyAuth, TokenBucketLimiter
from evidenceops.worker import IngestionWorker


class ToggleableProxy:
    def __init__(self, target_host: str, target_port: int) -> None:
        self._target = (target_host, target_port)
        self._server = socket.create_server(("127.0.0.1", 0))
        self._server.settimeout(0.05)
        self.port = self._server.getsockname()[1]
        self._up = True
        self._closed = False
        self._sockets: list[socket.socket] = []
        self._lock = threading.Lock()
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while not self._closed:
            try:
                client, _ = self._server.accept()
            except (TimeoutError, OSError):
                continue
            if not self._up:
                client.close()  # the "database" is unreachable
                continue
            upstream = socket.create_connection(self._target)
            with self._lock:
                self._sockets += [client, upstream]
            for source, sink in ((client, upstream), (upstream, client)):
                threading.Thread(target=self._pump, args=(source, sink), daemon=True).start()

    @staticmethod
    def _pump(source: socket.socket, sink: socket.socket) -> None:
        try:
            while data := source.recv(65536):
                sink.sendall(data)
        except OSError:
            pass
        finally:
            for sock in (source, sink):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def down(self) -> None:
        self._up = False
        with self._lock:
            sockets, self._sockets = self._sockets, []
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

    def up(self) -> None:
        self._up = True

    def close(self) -> None:
        self.down()
        self._closed = True
        self._server.close()


@contextmanager
def captured_logs():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("evidenceops")
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


@pytest.fixture
def proxy(test_settings, migrated_database):
    url = make_url(test_settings.database_dsn)
    proxy = ToggleableProxy(url.host or "localhost", url.port or 5432)
    try:
        yield proxy
    finally:
        proxy.close()


@pytest.fixture
def proxied_client(test_settings, proxy, clean_questions):
    url = make_url(test_settings.database_dsn).set(host="127.0.0.1", port=proxy.port)
    settings = test_settings.model_copy(update={
        "database_url": SecretStr(url.render_as_string(hide_password=False)),
    })
    with TestClient(create_app(settings, generator=FakeGenerator()), headers=AUTH_HEADERS) as client:
        yield client


# --- Liveness, readiness and database outages ----------------------------------------


def test_outage_returns_typed_503_and_recovers_without_restart(proxied_client, proxy, test_settings):
    client = proxied_client
    created = client.post("/questions", json={"text": "¿Asma?"}).json()["id"]
    assert client.get("/ready").json() == {"status": "ready", "checks": {"database": "ok", "migrations": "ok"}}

    proxy.down()
    password = make_url(test_settings.database_dsn).password
    with captured_logs() as logs:
        for response in (
            client.get(f"/questions/{created}"),
            client.post("/questions", json={"text": "otra"}),
            client.post(f"/questions/{created}/generate"),
            client.get(f"/ingestion-jobs/{uuid4()}"),
        ):
            assert response.status_code == 503
            assert response.json() == {"detail": {
                "code": "database_unavailable", "message": "Database is temporarily unavailable",
            }}
            for internal in ("Traceback", "psycopg", "5432", str(proxy.port), "SELECT"):
                assert internal not in response.text
        ready = client.get("/ready")
        assert ready.status_code == 503
        assert ready.json() == {"status": "not_ready",
                                "checks": {"database": "unavailable", "migrations": "unknown"}}
        assert client.get("/health").json() == {"status": "ok"}  # liveness unaffected
    events = [json.loads(line) for line in logs.getvalue().splitlines()]
    assert [e["cause"] for e in events if e["event"] == "database.unavailable"] == ["database_unavailable"] * 4
    if password:
        assert password not in logs.getvalue()
    assert "evidenceops_database_unavailable_total 4.0" in client.get("/metrics").text

    proxy.up()  # same process, same Engine: pre_ping replaces the dead connections
    assert client.get("/ready").status_code == 200
    assert client.get(f"/questions/{created}").status_code == 200
    assert client.post("/questions", json={"text": "vuelta"}).status_code == 201


def test_readiness_reports_outdated_migrations(client):
    client.app.state.migration_heads = frozenset({"not-the-current-head"})
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "ok", "migrations": "outdated"}


def test_programming_errors_are_not_disguised_as_outages(client, monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("bug")
    monkeypatch.setattr("evidenceops.main.jobs.get_job", broken)
    with pytest.raises(RuntimeError):
        client.get(f"/ingestion-jobs/{uuid4()}")


def test_worker_polling_backs_off_with_cap_and_resets():
    waits: list[float] = []
    outcomes = iter([OperationalError("x", {}, Exception())] * 5 + [False, "stop"])

    class Stop:
        def is_set(self):
            return False if not waits or waits[-1] != "stop" else True

        def wait(self, seconds):
            waits.append(seconds)

    class Worker(IngestionWorker):
        def run_once(self):
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            if outcome == "stop":
                waits.append("stop")
            return outcome

    settings = JobSettings(_env_file=None, poll_seconds=1, poll_backoff_max_seconds=5)
    Worker(None, None, settings, stop=Stop()).run()
    assert waits == [1, 2, 4, 5, 5, 1, "stop"]


# --- LLM total deadline -------------------------------------------------------------


class SlowGenerator:
    def __init__(self) -> None:
        self.release = threading.Event()
        self.seen_request_id = None

    def generate(self, question_text, *, system_instruction=None):
        self.seen_request_id = request_id.get()
        self.release.wait(5)
        return GeneratedContent(answer="late", limitations=[])

    def close(self):
        pass


def test_deadline_raises_typed_error_without_waiting_for_the_provider():
    slow = SlowGenerator()
    token = request_id.set("req-1")
    started = time.monotonic()
    try:
        with pytest.raises(GenerationError) as raised:
            DeadlineGenerator(slow, total_seconds=0.1).generate("q")
    finally:
        request_id.reset(token)
        slow.release.set()
    assert time.monotonic() - started < 1
    assert raised.value.cause == GenerationErrorCause.DEADLINE_EXCEEDED
    assert slow.seen_request_id == "req-1"  # context propagated to the call thread


def test_deadline_passes_through_results_and_provider_errors():
    class Failing:
        def generate(self, *_args, **_kwargs):
            raise GenerationError(GenerationErrorCause.RATE_LIMIT, "provider said no")

    assert DeadlineGenerator(FakeGenerator(), 5).generate("q").answer == "Respuesta generada para el test"
    with pytest.raises(GenerationError) as raised:
        DeadlineGenerator(Failing(), 5).generate("q")
    assert raised.value.cause == GenerationErrorCause.RATE_LIMIT


def test_deadline_maps_to_504_over_http(test_settings, clean_questions):
    slow = SlowGenerator()
    app = create_app(test_settings, generator=DeadlineGenerator(slow, total_seconds=0.1))
    try:
        with TestClient(app, headers=AUTH_HEADERS) as client:
            question = client.post("/questions", json={"text": "q"}).json()["id"]
            response = client.post(f"/questions/{question}/generate")
            metrics = client.get("/metrics").text
    finally:
        slow.release.set()
    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "generation_deadline_exceeded"
    assert 'evidenceops_generation_errors_total{cause="deadline_exceeded"} 1.0' in metrics


# --- Authentication -------------------------------------------------------------------


def test_protected_endpoints_require_a_valid_key(client):
    question = client.post("/questions", json={"text": "q"}).json()["id"]
    anonymous = TestClient(client.app)
    protected = [
        ("post", "/questions", {"text": "q"}),
        ("post", f"/questions/{question}/generate", None),
        ("post", "/rag", {"query": "asthma"}),
        ("post", "/ingestion-jobs", {"query": "asthma", "limit": 1}),
    ]
    for headers in ({}, {"X-API-Key": "wrong-key-0123456789"}, {"X-API-Key": "x" * 5000}):
        for method, path, body in protected:
            response = getattr(anonymous, method)(path, json=body, headers=headers)
            assert response.status_code == 401, path
            assert response.json() == {"detail": {"code": "unauthorized",
                                                  "message": "A valid API key is required"}}
            assert response.headers["www-authenticate"] == "ApiKey"
            assert "wrong-key" not in response.text
    valid = anonymous.post("/questions", json={"text": "q"}, headers=AUTH_HEADERS)
    assert valid.status_code == 201
    # Reads without cost stay open.
    for path in ("/health", "/ready", "/metrics", f"/questions/{question}"):
        assert anonymous.get(path).status_code == 200, path
    assert 'evidenceops_api_rejections_total{reason="unauthorized"} 12.0' in anonymous.get("/metrics").text


def test_auth_happens_before_validation_and_database_work(client):
    # Invalid body and unknown question still get 401 first: nothing is revealed.
    anonymous = TestClient(client.app)
    assert anonymous.post("/questions", json={"text": ""}).status_code == 401
    assert anonymous.post(f"/questions/{uuid4()}/generate").status_code == 401


def test_key_comparison_identifies_keys_without_revealing_them():
    auth = ApiKeyAuth((SecretStr("first-key-0123456789"), SecretStr("second-key-0123456789")))
    assert auth.identify("second-key-0123456789") == "key-1"
    assert auth.identify("second-key-012345678") is None  # prefix
    assert auth.identify(None) is None and auth.identify("") is None
    with pytest.raises(RuntimeError, match="EVIDENCEOPS_API_KEYS"):
        ApiKeyAuth(())


def test_api_refuses_to_start_without_keys(test_settings):
    settings = test_settings.model_copy(update={"api_keys": ()})
    with pytest.raises(RuntimeError, match="EVIDENCEOPS_API_KEYS"):
        with TestClient(create_app(settings, generator=FakeGenerator())):
            pass


def test_api_keys_from_environment_are_split_and_validated(monkeypatch):
    url = "postgresql+psycopg://user@localhost/evidenceops"
    monkeypatch.setenv("EVIDENCEOPS_API_KEYS", f" {TEST_API_KEY} , other-key-0123456789 ")
    keys = Settings(_env_file=None, database_url=url).api_keys
    assert [key.get_secret_value() for key in keys] == [TEST_API_KEY, "other-key-0123456789"]
    monkeypatch.setenv("EVIDENCEOPS_API_KEYS", "short-secret")
    with pytest.raises(ValidationError) as raised:
        Settings(_env_file=None, database_url=url)
    assert "short-secret" not in str(raised.value)


# --- Rate limiting -------------------------------------------------------------------


def test_token_bucket_bursts_then_refills():
    now = [0.0]
    limiter = TokenBucketLimiter(capacity=2, refill_per_second=0.5, clock=lambda: now[0])
    assert limiter.acquire("a") is None and limiter.acquire("a") is None
    assert limiter.acquire("a") == pytest.approx(2.0)  # empty: one token every 2 s
    assert limiter.acquire("b") is None  # buckets are per caller
    now[0] = 1.0
    assert limiter.acquire("a") == pytest.approx(1.0)
    now[0] = 2.0
    assert limiter.acquire("a") is None
    now[0] = 100.0
    assert [limiter.acquire("a") for _ in range(3)][:2] == [None, None]  # capped at capacity


def test_llm_endpoints_return_429_with_retry_after(test_settings, clean_questions):
    other = "other-key-0123456789"
    settings = test_settings.model_copy(update={
        "rate_limit_capacity": 1, "rate_limit_refill_per_second": 0.1,
        "api_keys": (SecretStr(TEST_API_KEY), SecretStr(other)),
    })
    with TestClient(create_app(settings, generator=FakeGenerator()), headers=AUTH_HEADERS) as client:
        question = client.post("/questions", json={"text": "q"}).json()["id"]
        assert client.post(f"/questions/{question}/generate").status_code == 200
        limited = client.post(f"/questions/{question}/generate")
        assert limited.status_code == 429
        assert limited.json()["detail"]["code"] == "rate_limited"
        assert 9 <= int(limited.headers["retry-after"]) <= 10
        assert client.post("/rag", json={"query": "asthma"}).status_code == 429  # shared bucket
        # Another key has its own bucket; non-LLM writes are not rate limited.
        assert client.post(f"/questions/{question}/generate",
                           headers={"X-API-Key": other}).status_code == 200
        assert all(client.post("/questions", json={"text": "q"}).status_code == 201 for _ in range(5))
        assert 'evidenceops_api_rejections_total{reason="rate_limited"} 2.0' in client.get("/metrics").text


# --- Secrets ---------------------------------------------------------------------------


def test_secrets_never_reach_repr_logs_errors_or_metrics(test_settings, clean_questions):
    sentinels = {
        "gemini": "gemini-secret-sentinel", "deepseek": "deepseek-secret-sentinel",
        "api": "api-secret-sentinel-0123", "db": "db-password-sentinel",
    }
    settings = Settings(
        _env_file=None,
        database_url=f"postgresql+psycopg://user:{sentinels['db']}@localhost/evidenceops",
        gemini_api_key=sentinels["gemini"], deepseek_api_key=sentinels["deepseek"],
        api_keys=(sentinels["api"],),
    )
    assert not any(value in repr(settings) or value in str(settings) or
                   value in settings.model_dump_json() for value in sentinels.values())
    with pytest.raises(ValidationError) as invalid:
        Settings(_env_file=None, database_url=f"postgresql://user:{sentinels['db']}@localhost/x")
    assert sentinels["db"] not in str(invalid.value)

    app_settings = test_settings.model_copy(update={
        "api_keys": (SecretStr(sentinels["api"]),),
        "gemini_api_key": SecretStr(sentinels["gemini"]),
    })
    with captured_logs() as logs, TestClient(
        create_app(app_settings, generator=FakeGenerator()), raise_server_exceptions=False,
    ) as client:
        good = {"X-API-Key": sentinels["api"]}
        bad = {"X-API-Key": sentinels["api"] + "-wrong"}
        question = client.post("/questions", json={"text": "q"}, headers=good).json()["id"]
        bodies = [
            client.post(f"/questions/{question}/generate", headers=good).text,
            client.post(f"/questions/{question}/generate", headers=bad).text,
            client.post("/rag", json={"query": ""}, headers=good).text,  # 422 echoes inputs only
            client.get("/ready").text,
            client.get("/metrics").text,
        ]
    observed = logs.getvalue() + "".join(bodies)
    assert not any(value in observed for value in sentinels.values())
    assert "api.request_rejected" in logs.getvalue()


def test_public_input_bounds():
    from evidenceops.schemas import RagRequest

    with pytest.raises(ValidationError):
        RagRequest(query="asthma", published_from=2**40)  # would overflow PostgreSQL integer
    assert RagRequest(query="asthma", published_from=2020).published_from == 2020

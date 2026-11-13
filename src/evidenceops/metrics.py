"""Prometheus metrics for generation and provider-reported usage."""

from collections.abc import Callable, Iterator

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector

from evidenceops.generation import GenerationErrorCause


class GenerationMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.generations = Counter(
            "evidenceops_generations_total", "Completed generation operations",
            ["outcome"], registry=self.registry,
        )
        self.errors = Counter(
            "evidenceops_generation_errors_total", "Generation errors by stable cause",
            ["cause"], registry=self.registry,
        )
        self.duration = Histogram(
            "evidenceops_generation_duration_seconds", "Generation operation duration",
            ["outcome"], buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, float("inf")),
            registry=self.registry,
        )
        self.rag_operations = Counter(
            "evidenceops_rag_operations_total", "Completed RAG operations and stages",
            ["stage", "outcome"], registry=self.registry,
        )
        self.rag_duration = Histogram(
            "evidenceops_rag_duration_seconds", "RAG operation and stage duration",
            ["stage", "outcome"], buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, float("inf")),
            registry=self.registry,
        )
        self.rag_errors = Counter(
            "evidenceops_rag_errors_total", "RAG operation and stage errors",
            ["stage", "cause"], registry=self.registry,
        )
        self.ingestion_jobs_enqueued = Counter(
            "evidenceops_ingestion_jobs_enqueued_total",
            "Ingestion enqueue requests; existing means an idempotent replay",
            ["outcome"], registry=self.registry,
        )
        self.api_rejections = Counter(
            "evidenceops_api_rejections_total", "Requests rejected by authentication or rate limiting",
            ["reason"], registry=self.registry,
        )
        self.database_unavailable = Counter(
            "evidenceops_database_unavailable_total",
            "API requests answered 503 because PostgreSQL was unreachable or timed out",
            registry=self.registry,
        )
        self.input_tokens = Counter(
            "evidenceops_llm_input_tokens_total", "Provider-reported input tokens",
            ["provider", "model"], registry=self.registry,
        )
        self.output_tokens = Counter(
            "evidenceops_llm_output_tokens_total", "Provider-reported output tokens",
            ["provider", "model"], registry=self.registry,
        )
        self.total_tokens = Counter(
            "evidenceops_llm_total_tokens_total", "Provider-reported total tokens",
            ["provider", "model"], registry=self.registry,
        )

    def record_rag(
        self, stage: str, outcome: str, duration: float, cause: str | None,
    ) -> None:
        self.rag_operations.labels(stage=stage, outcome=outcome).inc()
        self.rag_duration.labels(stage=stage, outcome=outcome).observe(duration)
        if cause is not None:
            self.rag_errors.labels(stage=stage, cause=cause).inc()

    def record_generation(
        self, outcome: str, duration_seconds: float,
        cause: GenerationErrorCause | None = None,
    ) -> None:
        self.generations.labels(outcome=outcome).inc()
        self.duration.labels(outcome=outcome).observe(duration_seconds)
        if cause is not None:
            self.errors.labels(cause=cause.value).inc()

    def record_unexpected_error(self, duration_seconds: float) -> None:
        self.record_generation("error", duration_seconds)
        self.errors.labels(cause="unexpected_application_error").inc()

    def record_usage(
        self, provider: str, model: str,
        input_tokens: int | None, output_tokens: int | None, total_tokens: int | None,
    ) -> None:
        values = (input_tokens, output_tokens, total_tokens)
        if any(type(value) is not int or value < 0 for value in values):
            return
        self.input_tokens.labels(provider=provider, model=model).inc(input_tokens)
        self.output_tokens.labels(provider=provider, model=model).inc(output_tokens)
        self.total_tokens.labels(provider=provider, model=model).inc(total_tokens)

    def render(self) -> bytes:
        return generate_latest(self.registry)


class _JobStatusCollector(Collector):
    """Queue depth read from PostgreSQL at scrape time: the table is the truth."""

    def __init__(self, count_by_status: Callable[[], dict[str, int]]) -> None:
        self._count_by_status = count_by_status

    def collect(self) -> Iterator[GaugeMetricFamily]:
        try:
            counts = self._count_by_status()
        except Exception:  # A failed scrape must not break the worker.
            return
        family = GaugeMetricFamily(
            "evidenceops_ingestion_jobs", "Ingestion jobs currently in each status", labels=["status"],
        )
        for status, count in sorted(counts.items()):
            family.add_metric([status], count)
        yield family


class JobMetrics:
    """Worker-process metrics; exposed by the worker, not by the API."""

    def __init__(self, count_by_status: Callable[[], dict[str, int]] | None = None) -> None:
        self.registry = CollectorRegistry()
        self.attempts = Counter(
            "evidenceops_ingestion_job_attempts_total", "Finished job attempts by outcome",
            ["outcome"], registry=self.registry,
        )
        self.duration = Histogram(
            "evidenceops_ingestion_job_duration_seconds", "Duration of one job attempt",
            ["outcome"], buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300, float("inf")),
            registry=self.registry,
        )
        self.retries = Counter(
            "evidenceops_ingestion_job_retries_total", "Attempts scheduled for retry by cause",
            ["cause"], registry=self.registry,
        )
        self.lease_expirations = Counter(
            "evidenceops_ingestion_job_lease_expirations_total",
            "Expired leases found: reclaimed by a worker or failed with no attempts left",
            ["action"], registry=self.registry,
        )
        if count_by_status is not None:
            self.registry.register(_JobStatusCollector(count_by_status))

    def record_attempt(self, outcome: str, duration_seconds: float) -> None:
        self.attempts.labels(outcome=outcome).inc()
        self.duration.labels(outcome=outcome).observe(duration_seconds)

    def render(self) -> bytes:
        return generate_latest(self.registry)

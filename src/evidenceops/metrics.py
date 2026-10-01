"""Prometheus metrics for generation and provider-reported usage."""

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

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

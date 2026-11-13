"""Select the configured generator without exposing providers to callers."""

from typing import Protocol

import contextvars
import threading
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError

from evidenceops.config import GenerationSettings
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause, Generator
from evidenceops.metrics import GenerationMetrics


class OwnedGenerator(Generator, Protocol):
    def close(self) -> None: ...


class DeadlineGenerator:
    """Bound the total wall-clock time of each generate() call.

    Transport timeouts apply to each HTTP operation (connect, each read), and
    the Gemini SDK may retry once, so they do not bound a call in total. The
    provider call runs in a daemon thread and the caller waits at most
    ``total_seconds``. Python cannot kill that thread: after the deadline the
    request is abandoned, not cancelled. It may still finish and consume quota,
    and it ends at the latest when its transport timeouts fire (D037).
    """

    def __init__(self, inner: "OwnedGenerator", total_seconds: float) -> None:
        self.inner = inner
        self._total_seconds = total_seconds

    def generate(
        self, question_text: str, *, system_instruction: str | None = None,
    ) -> GeneratedContent:
        future: Future[GeneratedContent] = Future()
        # Carry request_id and the active span into the worker thread.
        context = contextvars.copy_context()

        def call() -> None:
            try:
                future.set_result(context.run(
                    self.inner.generate, question_text, system_instruction=system_instruction,
                ))
            except BaseException as exc:  # delivered to the waiting caller
                future.set_exception(exc)

        threading.Thread(target=call, name="llm-call", daemon=True).start()
        try:
            return future.result(timeout=self._total_seconds)
        except FutureTimeoutError:
            raise GenerationError(
                GenerationErrorCause.DEADLINE_EXCEEDED,
                "Generation exceeded its total time limit",
            ) from None

    def close(self) -> None:
        self.inner.close()


def create_generator(settings: GenerationSettings, metrics: GenerationMetrics | None = None) -> OwnedGenerator:
    return DeadlineGenerator(_create_provider(settings, metrics), settings.llm_total_timeout_seconds)


def _create_provider(settings: GenerationSettings, metrics: GenerationMetrics | None) -> OwnedGenerator:
    if settings.llm_provider == "gemini":
        if settings.gemini_api_key is None:
            raise RuntimeError("EVIDENCEOPS_GEMINI_API_KEY is required for generation")
        from evidenceops.gemini import GeminiGenerator

        return GeminiGenerator(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            max_output_tokens=settings.gemini_max_output_tokens,
            timeout_seconds=settings.gemini_timeout_seconds,
            metrics=metrics,
        )
    if settings.llm_provider == "deepseek":
        if settings.deepseek_api_key is None:
            raise RuntimeError("EVIDENCEOPS_DEEPSEEK_API_KEY is required for generation")
        from evidenceops.deepseek import DeepSeekGenerator

        return DeepSeekGenerator(
            api_key=settings.deepseek_api_key.get_secret_value(),
            model=settings.deepseek_model,
            max_output_tokens=settings.deepseek_max_output_tokens,
            timeout_seconds=settings.deepseek_timeout_seconds,
            metrics=metrics,
        )
    raise ValueError("Unsupported EVIDENCEOPS_LLM_PROVIDER")

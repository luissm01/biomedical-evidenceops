"""Select the configured generator without exposing providers to callers."""

from typing import Protocol

from evidenceops.config import GenerationSettings
from evidenceops.generation import Generator


class OwnedGenerator(Generator, Protocol):
    def close(self) -> None: ...


def create_generator(settings: GenerationSettings) -> OwnedGenerator:
    if settings.llm_provider == "gemini":
        if settings.gemini_api_key is None:
            raise RuntimeError("EVIDENCEOPS_GEMINI_API_KEY is required for generation")
        from evidenceops.gemini import GeminiGenerator

        return GeminiGenerator(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            max_output_tokens=settings.gemini_max_output_tokens,
            timeout_seconds=settings.gemini_timeout_seconds,
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
        )
    raise ValueError("Unsupported EVIDENCEOPS_LLM_PROVIDER")

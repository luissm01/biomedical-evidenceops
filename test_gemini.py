"""Manual inference only: uv run --locked python test_gemini.py."""

from contextlib import closing

from evidenceops.config import Settings
from evidenceops.gemini import GeminiGenerator


def main() -> None:
    settings = Settings()
    if settings.gemini_api_key is None:
        raise SystemExit("EVIDENCEOPS_GEMINI_API_KEY is required for generation")

    with closing(
        GeminiGenerator(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            max_output_tokens=settings.gemini_max_output_tokens,
            timeout_seconds=settings.gemini_timeout_seconds,
        )
    ) as generator:
        result = generator.generate(
            "¿Qué evidencia existe sobre el uso de semaglutida "
            "para reducir eventos cardiovasculares?"
        )
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

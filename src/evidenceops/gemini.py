"""Gemini adapter: structured inference and validation at the provider boundary."""

from collections.abc import Iterator

import httpx
from google import genai
from google.genai import types
from pydantic import ValidationError

from evidenceops.generation import (
    GeneratedContent,
    GenerationError,
    GenerationErrorCause,
)


SYSTEM_INSTRUCTION = """
Eres un asistente especializado en preguntas biomédicas.

Responde a la pregunta de forma clara, prudente y útil utilizando únicamente
el conocimiento disponible en el modelo.

El campo `answer` debe contener la respuesta a la pregunta biomédica.

No proporciones estudios, citas, cifras o resultados específicos si no tienes
suficiente certeza. Expresa la incertidumbre cuando corresponda.

El campo `limitations` debe contener una lista de limitaciones relevantes de
la respuesta o de la propia pregunta. Incluye, cuando corresponda, información
importante que falte para poder responder con mayor precisión.

No afirmes que has consultado, buscado o verificado información en fuentes
externas.
"""


_RETRIABLE_STATUS_CODES = [
    408,
    500,
    502,
    503,
    504,
]

_SAFE_ERROR_MESSAGES = {
    GenerationErrorCause.TIMEOUT:
        "Gemini did not complete the request in time",
    GenerationErrorCause.RATE_LIMIT:
        "Gemini rate limit was reached",
    GenerationErrorCause.AUTHENTICATION:
        "Gemini authentication failed",
    GenerationErrorCause.PROVIDER_UNAVAILABLE:
        "Gemini is temporarily unavailable",
    GenerationErrorCause.UNKNOWN:
        "An unexpected error occurred while generating the answer",
}


def _exception_chain(exc: BaseException) -> Iterator[BaseException]:
    """Walk explicit exception causes without depending on SDK-private classes."""
    current: BaseException | None = exc
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__


def _provider_status_code(exc: BaseException) -> int | None:
    """
    Extract an HTTP status from both google-genai error paths.

    Classic SDK errors expose `code`.
    Interactions errors expose `status_code`.
    """
    for current in _exception_chain(exc):
        status_code = getattr(current, "status_code", None)
        if isinstance(status_code, int):
            return status_code

        code = getattr(current, "code", None)
        if isinstance(code, int):
            return code

    return None


def _classify_provider_error(exc: BaseException) -> GenerationErrorCause:
    chain = tuple(_exception_chain(exc))

    if any(isinstance(error, httpx.TimeoutException) for error in chain):
        return GenerationErrorCause.TIMEOUT

    status_code = _provider_status_code(exc)

    if status_code == 408:
        return GenerationErrorCause.TIMEOUT

    if status_code == 429:
        return GenerationErrorCause.RATE_LIMIT

    if status_code in {401, 403}:
        return GenerationErrorCause.AUTHENTICATION

    if status_code is not None and 500 <= status_code < 600:
        return GenerationErrorCause.PROVIDER_UNAVAILABLE

    if any(isinstance(error, httpx.RequestError) for error in chain):
        return GenerationErrorCause.PROVIDER_UNAVAILABLE

    return GenerationErrorCause.UNKNOWN


class GeminiGenerator:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.6-flash",
        max_output_tokens: int = 2048,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError(
                "EVIDENCEOPS_GEMINI_API_KEY is required for generation"
            )

        self._model = model
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds

        try:
            self._client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    retry_options=types.HttpRetryOptions(
                        # Interactions 2.23.0 interprets this as
                        # at most one retry after the first attempt.
                        attempts=1,
                        http_status_codes=_RETRIABLE_STATUS_CODES,
                        initial_delay=0.5,
                        # Backoff cap only: the SDK may honor a longer Retry-After.
                        max_delay=0.5,
                        jitter=0,
                    ),
                ),
            )
        except Exception as exc:
            raise GenerationError(
                cause=GenerationErrorCause.UNKNOWN,
                message="Could not initialize the Gemini client",
            ) from exc

    def close(self) -> None:
        """Release the reusable synchronous SDK client."""
        try:
            self._client.close()
        except Exception as exc:
            raise GenerationError(
                cause=GenerationErrorCause.UNKNOWN,
                message="Could not close the Gemini client",
            ) from exc

    def generate(self, question_text: str) -> GeneratedContent:
        try:
            interaction = self._client.interactions.create(
                model=self._model,
                system_instruction=SYSTEM_INSTRUCTION,
                input=question_text,
                store=False,
                generation_config={
                    "max_output_tokens": self._max_output_tokens
                },
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": GeneratedContent.model_json_schema(),
                },
                timeout=self._timeout_seconds,
            )

            output_text = interaction.output_text

        except Exception as exc:
            cause = _classify_provider_error(exc)

            raise GenerationError(
                cause=cause,
                message=_SAFE_ERROR_MESSAGES[cause],
            ) from exc

        try:
            return GeneratedContent.model_validate_json(output_text)

        except ValidationError as exc:
            raise GenerationError(
                cause=GenerationErrorCause.INVALID_OUTPUT,
                message="Gemini output did not match the expected schema",
            ) from exc

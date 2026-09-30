"""DeepSeek Chat Completions adapter with validated JSON output."""

import logging

import httpx
from pydantic import ValidationError

from evidenceops.generation_prompt import SYSTEM_INSTRUCTION
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause

logger = logging.getLogger(__name__)
_ENDPOINT = "https://api.deepseek.com/chat/completions"
_SAFE_MESSAGES = {
    GenerationErrorCause.TIMEOUT: "DeepSeek did not complete the request in time",
    GenerationErrorCause.RATE_LIMIT: "DeepSeek rate limit was reached",
    GenerationErrorCause.AUTHENTICATION: "DeepSeek authentication failed",
    GenerationErrorCause.PROVIDER_UNAVAILABLE: "DeepSeek is temporarily unavailable",
    GenerationErrorCause.UNKNOWN: "An unexpected error occurred while generating the answer",
}


class DeepSeekGenerator:
    def __init__(
        self, api_key: str, model: str = "deepseek-flash",
        max_output_tokens: int = 2048, timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("EVIDENCEOPS_DEEPSEEK_API_KEY is required for generation")
        self._model = model
        self._max_output_tokens = max_output_tokens
        try:
            self._client = httpx.Client(
                timeout=timeout_seconds,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        except Exception as exc:
            raise GenerationError(GenerationErrorCause.UNKNOWN, "Could not initialize the DeepSeek client") from exc

    def close(self) -> None:
        try:
            self._client.close()
        except Exception as exc:
            raise GenerationError(GenerationErrorCause.UNKNOWN, "Could not close the DeepSeek client") from exc

    def generate(self, question_text: str) -> GeneratedContent:
        logger.info("llm.generation.started", extra={"provider": "deepseek", "model": self._model})
        try:
            response = self._client.post(_ENDPOINT, json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": SYSTEM_INSTRUCTION +
                     '\nDevuelve solo JSON con esta estructura: '
                     '{"answer": "respuesta prudente", "limitations": ["limitación relevante"]}.'},
                    {"role": "user", "content": question_text},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": self._max_output_tokens,
                "stream": False,
            })
            response.raise_for_status()
        except Exception as exc:
            cause = self._classify_error(exc)
            raise GenerationError(cause, _SAFE_MESSAGES[cause]) from exc

        try:
            payload = response.json()
            choice = payload["choices"][0]
            if choice["finish_reason"] != "stop":
                raise ValueError("Incomplete output")
            return GeneratedContent.model_validate_json(choice["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
            raise GenerationError(
                GenerationErrorCause.INVALID_OUTPUT,
                "DeepSeek output did not match the expected schema",
            ) from exc

    @staticmethod
    def _classify_error(exc: Exception) -> GenerationErrorCause:
        if isinstance(exc, httpx.TimeoutException):
            return GenerationErrorCause.TIMEOUT
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status == 408:
                return GenerationErrorCause.TIMEOUT
            if status == 429:
                return GenerationErrorCause.RATE_LIMIT
            if status in {401, 403}:
                return GenerationErrorCause.AUTHENTICATION
            if status == 402 or 500 <= status < 600:
                return GenerationErrorCause.PROVIDER_UNAVAILABLE
        if isinstance(exc, httpx.RequestError):
            return GenerationErrorCause.PROVIDER_UNAVAILABLE
        return GenerationErrorCause.UNKNOWN

"""Gemini adapter: structured inference and validation at the provider boundary."""

from google import genai
from google.genai import types
from pydantic import ValidationError

from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause


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


class GeminiGenerator:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.6-flash",
        max_output_tokens: int = 2048,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("EVIDENCEOPS_GEMINI_API_KEY is required for generation")
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        try:
            self._client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    # 2.23.0 still retries once in Interactions; see #11.
                    retry_options=types.HttpRetryOptions(attempts=0),
                ),
            )
        except Exception as exc:
            raise GenerationError(
                cause=GenerationErrorCause.UNKNOWN,
                message="Could not initialize the Gemini client",
            ) from exc

    def close(self) -> None:
        """Release the reusable synchronous SDK client; owner calls this once done."""
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
                generation_config={"max_output_tokens": self._max_output_tokens},
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": GeneratedContent.model_json_schema(),
                },
                timeout=self._timeout_seconds,
            )
            output_text = interaction.output_text
        except Exception as exc:
            raise GenerationError(
                cause=GenerationErrorCause.UNKNOWN,
                message="An unexpected error occurred while generating the answer",
            ) from exc

        try:
            return GeneratedContent.model_validate_json(output_text)
        except ValidationError as exc:
            raise GenerationError(
                cause=GenerationErrorCause.INVALID_OUTPUT,
                message="Gemini output did not match the expected schema",
            ) from exc

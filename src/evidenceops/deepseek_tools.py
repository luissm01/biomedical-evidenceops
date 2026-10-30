"""DeepSeek non-thinking native tool calling, separate from Generator/RAG."""

import logging

import httpx
from pydantic import ValidationError

from evidenceops.config import GenerationSettings
from evidenceops.deepseek import DeepSeekGenerator, _ENDPOINT, _SAFE_MESSAGES
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause
from evidenceops.metrics import GenerationMetrics
from evidenceops.tool_calling import TOOL_SYSTEM_INSTRUCTION, ToolProposal
from evidenceops.tools import ToolCall, ToolCallingError, ToolDefinition, ToolResult, compact_json
from evidenceops.tracing import traced_provider

logger = logging.getLogger(__name__)


class DeepSeekToolCaller:
    """Own its HTTP client; no retries, hidden tool execution or stored conversation."""

    def __init__(self, api_key: str, model: str = "deepseek-flash", *,
                 max_output_tokens: int = 2048, timeout_seconds: float = 60.0,
                 metrics: GenerationMetrics | None = None,
                 transport: httpx.BaseTransport | None = None):
        if not api_key.strip():
            raise ValueError("EVIDENCEOPS_DEEPSEEK_API_KEY is required for tool calling")
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._metrics = metrics
        self._client = httpx.Client(timeout=timeout_seconds, transport=transport,
                                    headers={"Authorization": f"Bearer {api_key}"})

    def close(self) -> None:
        self._client.close()

    def _request(self, messages: list[dict], *, tools: list[dict] | None = None) -> dict:
        logger.info("llm.generation.started", extra={"provider": "deepseek", "model": self._model})
        body = {"model": self._model, "messages": messages, "stream": False,
                "max_tokens": self._max_output_tokens, "thinking": {"type": "disabled"}}
        if tools is not None:
            body.update(tools=tools, tool_choice="auto")
        else:
            body.update(tool_choice="none", response_format={"type": "json_object"})
        try:
            response = self._client.post(_ENDPOINT, json=body)
            response.raise_for_status()
        except Exception as exc:
            cause = DeepSeekGenerator._classify_error(exc)
            raise GenerationError(cause, _SAFE_MESSAGES[cause]) from exc
        try:
            payload = response.json()
            usage = payload.get("usage")
            if self._metrics is not None and isinstance(usage, dict):
                self._metrics.record_usage("deepseek", self._model,
                    usage.get("prompt_tokens"), usage.get("completion_tokens"), usage.get("total_tokens"))
            choices = payload["choices"]
            if len(choices) != 1:
                raise ValueError("Expected one choice")
            choice = choices[0]
            if choice["finish_reason"] not in {"stop", "tool_calls"}:
                raise ValueError("Incomplete output")
            message = choice["message"]
            if not isinstance(message, dict) or message.get("role", "assistant") != "assistant":
                raise ValueError("Invalid assistant message")
            if choice["finish_reason"] == "tool_calls" and not message.get("tool_calls"):
                raise ValueError("Missing tool call")
            return message
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise _invalid_output() from exc

    @staticmethod
    def _messages(question: str) -> list[dict]:
        return [{"role": "system", "content": TOOL_SYSTEM_INSTRUCTION},
                {"role": "user", "content": question}]

    @traced_provider("deepseek")
    def propose(self, question: str, tools: tuple[ToolDefinition, ...]) -> ToolProposal | GeneratedContent:
        definitions = [{"type": "function", "function": {"name": tool.name,
            "description": tool.description, "parameters": tool.arguments.model_json_schema()}}
            for tool in tools]
        message = self._request(self._messages(question), tools=definitions)
        calls = message.get("tool_calls")
        if not calls:
            return _content(message)
        if not isinstance(calls, list):
            raise _invalid_output()
        if len(calls) > 1:
            raise ToolCallingError("call_limit_exceeded")
        try:
            call = calls[0]
            if call["type"] != "function":
                raise ValueError("Expected function call")
            proposal = ToolProposal(ToolCall(id=call["id"], name=call["function"]["name"],
                                            arguments=call["function"]["arguments"]),
                                    assistant_text=message.get("content"))
            if proposal.assistant_text is not None and not isinstance(proposal.assistant_text, str):
                raise ValueError("Invalid assistant text")
            return proposal
        except (ValueError, KeyError, TypeError, ValidationError) as exc:
            raise _invalid_output() from exc

    @traced_provider("deepseek")
    def finalize(self, question: str, proposal: ToolProposal, result: ToolResult) -> GeneratedContent:
        call = proposal.call
        if result.call_id != call.id or result.tool != call.name:
            raise ToolCallingError("invalid_call")
        messages = [*self._messages(question),
            {"role": "assistant", "content": proposal.assistant_text, "tool_calls": [
                {"id": call.id, "type": "function", "function": {
                    "name": call.name, "arguments": call.arguments}}]},
            {"role": "tool", "tool_call_id": call.id, "content": compact_json(result.payload())}]
        message = self._request(messages)
        if message.get("tool_calls"):
            raise ToolCallingError("round_limit_exceeded")
        return _content(message)


def _invalid_output() -> GenerationError:
    return GenerationError(GenerationErrorCause.INVALID_OUTPUT, "DeepSeek tool output did not match the expected schema")


def _content(message: dict) -> GeneratedContent:
    try:
        return GeneratedContent.model_validate_json(message["content"])
    except (ValueError, KeyError, TypeError, ValidationError) as exc:
        raise _invalid_output() from exc


def create_deepseek_tool_caller(settings: GenerationSettings,
                               metrics: GenerationMetrics | None = None) -> DeepSeekToolCaller:
    """Tool calling explicitly uses DeepSeek, independent of the Generator selector."""
    if settings.deepseek_api_key is None:
        raise ValueError("EVIDENCEOPS_DEEPSEEK_API_KEY is required for tool calling")
    return DeepSeekToolCaller(settings.deepseek_api_key.get_secret_value(), model=settings.deepseek_model,
        max_output_tokens=settings.deepseek_max_output_tokens, timeout_seconds=settings.deepseek_timeout_seconds,
        metrics=metrics)

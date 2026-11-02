"""Synchronous agent adapter owning one MCP v2 stdio client and subprocess."""

from contextlib import ExitStack, contextmanager
import os
import sys

from anyio.from_thread import start_blocking_portal
from mcp import Client, StdioServerParameters
from mcp.shared.exceptions import MCPError
from mcp.types import REQUEST_TIMEOUT
from pydantic import ValidationError

from evidenceops.mcp_server import tool_catalog
from evidenceops.tools import (
    RESULT_CHARACTER_LIMIT, TOOL_BUDGET_SECONDS, GetPublicationArgs, PublicationDetails,
    ToolCall, ToolCallingError,
    ToolResult, compact_json, validate_tool_call,
)

# These are the executor's controlled failures, never arbitrary remote error text.
REMOTE_ERROR_CODES = {
    "unknown_tool", "invalid_arguments", "invalid_call", "sql_timeout", "tool_timeout",
    "tool_budget_exceeded", "backend_error", "result_too_large",
}


class MCPToolExecutor:
    def __init__(self, portal, client):
        self._portal, self._client = portal, client

    validate = staticmethod(validate_tool_call)

    def execute(self, call: ToolCall) -> ToolResult:
        arguments = self.validate(call)
        try:
            result = self._portal.call(self._client.session.call_tool, call.name,
                                       arguments.model_dump(mode="json"), TOOL_BUDGET_SECONDS)
        except MCPError as exc:
            raise ToolCallingError("tool_timeout" if exc.code == REQUEST_TIMEOUT
                                   else "mcp_connection_error") from None
        except (RuntimeError, ValidationError):
            raise ToolCallingError("mcp_contract_error") from None
        except TimeoutError:
            raise ToolCallingError("tool_timeout") from None
        except Exception:
            raise ToolCallingError("mcp_connection_error") from None
        payload = result.structured_content
        if result.is_error:
            code = payload.get("code") if isinstance(payload, dict) else None
            raise ToolCallingError(code if isinstance(code, str) and code in REMOTE_ERROR_CODES else "mcp_contract_error")
        try:
            if len(compact_json(payload)) > RESULT_CHARACTER_LIMIT:
                raise ToolCallingError("result_too_large")
            parsed = ToolResult.model_validate(payload)
            if parsed.tool != call.name:
                raise ToolCallingError("mcp_contract_error")
            if (isinstance(arguments, GetPublicationArgs) and isinstance(parsed.data, PublicationDetails)
                and parsed.data.publication_id != arguments.publication_id):
                raise ToolCallingError("mcp_contract_error")
            # MCP request IDs and native LLM call IDs are separate namespaces.
            correlated = parsed.model_copy(update={"call_id": call.id})
            if len(compact_json(correlated.payload())) > RESULT_CHARACTER_LIMIT:
                raise ToolCallingError("result_too_large")
            return correlated
        except (ValueError, TypeError, ValidationError):
            raise ToolCallingError("mcp_contract_error") from None


@contextmanager
def connect_mcp_tools(parameters: StdioServerParameters | None = None):
    """Discover and check the local contract before giving an executor to the graph.

    The caller owns this context for the whole run. No reconnects or retries.
    Custom parameters are for trusted local commands (e.g. deterministic tests).
    """
    parameters = parameters or StdioServerParameters(
        command=sys.executable, args=["-m", "evidenceops.mcp_server"],
        env={key: os.environ[key] for key in (
            "EVIDENCEOPS_DATABASE_URL", "HF_HOME", "HF_HUB_CACHE", "HF_HUB_OFFLINE",
            "TRANSFORMERS_OFFLINE",
        ) if key in os.environ},
    )
    with start_blocking_portal() as portal, ExitStack() as stack:
        try:
            manager = portal.wrap_async_context_manager(Client(
                parameters, read_timeout_seconds=TOOL_BUDGET_SECONDS, cache=None,
            ))
            client = manager.__enter__()
            # Close without injecting the caller's exception into SDK task groups:
            # otherwise AnyIO wraps our public error in nested ExceptionGroups.
            stack.callback(manager.__exit__, None, None, None)
            discovered = portal.call(client.list_tools)
        except Exception:
            raise ToolCallingError("mcp_connection_error") from None
        expected = {t.name: t for t in tool_catalog()}
        if (len(discovered.tools) != len(expected) or discovered.next_cursor is not None
            or any(t.name not in expected or t.input_schema != expected[t.name].input_schema
                   or t.output_schema != expected[t.name].output_schema for t in discovered.tools)
            or {t.name for t in discovered.tools} != set(expected)):
            raise ToolCallingError("mcp_contract_error")
        yield MCPToolExecutor(portal, client)

"""Local stdio MCP v2 boundary over the existing read-only executor."""

from uuid import uuid4

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool, ToolAnnotations

from evidenceops.tools import (
    TOOL_DEFINITIONS, ToolCall, ToolCallingError, ToolExecutor, ToolResult, compact_json,
)


def tool_catalog() -> list[Tool]:
    return [Tool(name=d.name, description=d.description,
                 input_schema=d.arguments.model_json_schema(),
                 output_schema=ToolResult.model_json_schema(),
                 annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                             idempotent_hint=True, open_world_hint=False))
            for d in TOOL_DEFINITIONS]


def create_mcp_server(executor: ToolExecutor) -> Server:
    async def list_tools(context, params):
        return ListToolsResult(tools=tool_catalog())

    async def call_tool(context, params):
        try:
            if params.name not in {d.name for d in TOOL_DEFINITIONS}:
                raise ToolCallingError("unknown_tool")
            call = ToolCall(id=uuid4().hex, name=params.name,
                            arguments=compact_json(params.arguments or {}))
            result = await anyio.to_thread.run_sync(executor.execute, call)
            payload = result.payload()
            return CallToolResult(content=[TextContent(type="text", text=compact_json(payload))],
                                  structured_content=payload)
        except ToolCallingError as exc:
            code = exc.code
        except Exception:
            code = "backend_error"
        # Fixed public codes only: no SQL, arguments, abstracts or exception messages.
        return CallToolResult(is_error=True, structured_content={"code": code},
                              content=[TextContent(type="text", text=code)])

    return Server("Biomedical EvidenceOps", version="0.1.0",
                  on_list_tools=list_tools, on_call_tool=call_tool)


async def serve(executor: ToolExecutor) -> None:
    server = create_mcp_server(executor)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    from evidenceops.config import Settings
    from evidenceops.database import create_database
    from evidenceops.embeddings import LocalMedCPT
    from evidenceops.tools import create_tool_executor

    engine, sessions = create_database(Settings())
    try:
        anyio.run(serve, create_tool_executor(sessions, LocalMedCPT()))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

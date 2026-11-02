"""Test-only stdio composition: real PostgreSQL, deterministic query encoder."""

import anyio

from evidenceops.config import Settings
from evidenceops.database import create_database
from evidenceops.mcp_server import serve
from evidenceops.tools import create_tool_executor
from test_retrieval import ControlledMedCPT

settings = Settings()
# Same isolation guard as the main database fixtures; never run against user data.
if settings.database_url.path != "/evidenceops_test":
    raise RuntimeError("MCP test server requires evidenceops_test")
engine, sessions = create_database(settings)
try:
    anyio.run(serve, create_tool_executor(sessions, ControlledMedCPT()))
finally:
    engine.dispose()

"""Real stdio + real read services/PostgreSQL; no real LLM or embeddings."""

from pathlib import Path
import sys
from uuid import uuid4

from mcp import StdioServerParameters
from sqlalchemy import delete

from evidenceops.agent import AgentService
from evidenceops.mcp_client import connect_mcp_tools
from evidenceops.models import Publication
from evidenceops.retrieval import index_publication
from evidenceops.tools import create_tool_executor
from test_tools_integration import database
from test_retrieval import ControlledMedCPT, document, persist
from test_tools import call
from test_agent import answer, proposal, scripted


def test_stdio_services_and_graph_against_postgres(database, test_settings, monkeypatch):
    sessions = database
    encoder = ControlledMedCPT()
    identifier = persist(sessions, document(source_id=f"mcp-{uuid4()}", year=9999))
    try:
        index_publication(sessions, identifier, encoder)
        params = StdioServerParameters(command=sys.executable,
            args=[str(Path(__file__).with_name("mcp_db_server.py"))],
            env={"EVIDENCEOPS_DATABASE_URL": test_settings.database_dsn})
        with connect_mcp_tools(params) as remote:
            search_call = call(arguments={"query": "discovery", "published_from": 9999})
            direct = create_tool_executor(sessions, encoder)
            assert remote.execute(search_call).payload() == direct.execute(search_call).payload()
            read_call = call("get_publication", {"publication_id": str(identifier)})
            assert remote.execute(read_call).payload() == direct.execute(read_call).payload()
            missing = call("get_publication", {"publication_id": str(uuid4())})
            assert remote.execute(missing).error.code == "publication_not_found"
            model = scripted(proposal(arguments={"query": "discovery", "published_from": 9999}),
                proposal("get_publication", {"publication_id": str(identifier)}, "read"),
                answer("Abstract consultado [S1]."))
            response = AgentService(model, remote).run("discovery")
        monkeypatch.setenv("EVIDENCEOPS_DATABASE_URL", test_settings.database_dsn)
        # Normal production composition reads DB through stdio without loading MedCPT
        # for bibliographic lookup. Also verifies explicit environment propagation.
        with connect_mcp_tools() as production:
            assert production.execute(read_call).payload() == direct.execute(read_call).payload()
        assert response.status == "answered"
        assert (response.llm_calls, response.tool_calls, response.steps) == (3, 2, 6)
        assert response.sources[0].publication_id == identifier
        assert response.sources[0].abstract == "Treatment evidence"
        with sessions() as session:
            assert session.get(Publication, identifier).abstract == "Treatment evidence"
    finally:
        with sessions.begin() as session:
            session.execute(delete(Publication).where(Publication.id == identifier))

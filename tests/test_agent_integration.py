"""Real read services/DB with deterministic encoder and model; no inference."""

import json
from uuid import uuid4

from sqlalchemy import delete

from evidenceops.agent import AgentService
from evidenceops.generation import GeneratedContent
from evidenceops.models import Publication
from evidenceops.retrieval import index_publication
from evidenceops.tool_calling import ToolProposal
from evidenceops.tools import create_tool_executor
from test_retrieval import ControlledMedCPT, document, persist
from test_tools import call
from test_tools_integration import database


def test_graph_search_read_answer_reuses_services_and_releases_connections(database):
    sessions = database
    encoder = ControlledMedCPT()
    # Synthetic future year isolates discovery from any existing fixture corpus.
    publication_id = persist(sessions, document(source_id=f"agent-{uuid4()}", year=9999))
    try:
        index_publication(sessions, publication_id, encoder)
        class Model:
            def decide(self, messages, tools, *, timeout_seconds):
                assert sessions.kw["bind"].pool.checkedout() == 0
                assert timeout_seconds > 0
                if len(messages) == 2:
                    return ToolProposal(call(arguments={"query": "discovery", "published_from": 9999}))
                result = json.loads(messages[-1]["content"])
                if result["tool"] == "search_evidence":
                    assert result["data"]["items"][0]["publication_id"] == str(publication_id)
                    assert "abstract" not in result["data"]["items"][0]
                    invocation = call("get_publication", {"publication_id": str(publication_id)})
                    return ToolProposal(invocation.model_copy(update={"id": "read_1"}))
                assert result["data"]["abstract"] == "Treatment evidence"
                assert result["data"]["citation_id"] == "S1"
                return GeneratedContent(answer="Abstract consultado [S1].", limitations=[])
        response = AgentService(Model(), create_tool_executor(sessions, encoder)).run("discovery")
        assert response.status == "answered" and response.termination_reason == "final_answer"
        assert response.sources[0].publication_id == publication_id
        assert response.sources[0].detail_level == "abstract"
        assert (response.llm_calls, response.tool_calls, response.steps) == (3, 2, 6)
        assert encoder.query_calls == ["discovery"] and len(encoder.article_calls) == 1
        with sessions() as session:
            assert session.get(Publication, publication_id).abstract == "Treatment evidence"
    finally:
        with sessions.begin() as session:
            session.execute(delete(Publication).where(Publication.id == publication_id))

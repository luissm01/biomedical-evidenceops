"""MCP stdio + real LangGraph, with a deterministic model and no LLM calls."""

import argparse
from dataclasses import asdict
import json
import sys

from mcp import StdioServerParameters

from evidenceops.agent import AgentService
from evidenceops.generation import GeneratedContent
from evidenceops.mcp_client import connect_mcp_tools
from evidenceops.rag import ABSTENTION_ANSWER
from evidenceops.tool_calling import ToolProposal
from evidenceops.tools import ToolCall, compact_json


class DemoModel:
    """Scripted discovery -> read first actual ID -> acknowledge/abstain."""

    def __init__(self, query: str):
        self.query = query

    def decide(self, messages, tools, *, timeout_seconds):
        if len(messages) == 2:
            return ToolProposal(ToolCall(id="discover", name="search_evidence",
                                         arguments=compact_json({"query": self.query})))
        result = json.loads(messages[-1]["content"])
        if result["tool"] == "search_evidence" and result["data"]["items"]:
            identifier = result["data"]["items"][0]["publication_id"]
            return ToolProposal(ToolCall(id="read", name="get_publication",
                                         arguments=compact_json({"publication_id": identifier})))
        if result["tool"] == "get_publication" and result["status"] == "ok" and result["data"]["abstract"]:
            return GeneratedContent(answer="Se consultó un abstract del corpus local [S1].", limitations=[])
        return GeneratedContent(answer=ABSTENTION_ANSWER, limitations=[])


def fixture_executor():
    """Explicit synthetic server composition; never used by the normal server."""
    from evidenceops.biomedical import BiomedicalDocument
    from evidenceops.chunking import build_retrievable_unit
    from evidenceops.retrieval import RetrievalResult
    from evidenceops.tool_calling_demo import PUBLICATION_ID
    from evidenceops.tools import ToolExecutor

    document = BiomedicalDocument(source="pubmed", source_id="mcp-fixture", title="Synthetic MCP fixture",
        abstract="Synthetic abstract; no clinical claims.", authors=["Fixture Group"],
        journal=None, doi=None, publication_year=None, source_url=None)
    unit = build_retrievable_unit(document, publication_id=PUBLICATION_ID)
    return ToolExecutor(lambda **kw: [RetrievalResult(unit, 1.0)],
                        lambda identifier: document if identifier == PUBLICATION_ID else None)


def run_demo(query: str, *, local_db: bool = False) -> dict:
    parameters = None if local_db else StdioServerParameters(
        command=sys.executable, args=["-m", "evidenceops.mcp_demo", "--fixture-server"],
    )
    with connect_mcp_tools(parameters) as executor:
        response = AgentService(DemoModel(query), executor).run(query)
    result = asdict(response)
    result["content"] = response.content.model_dump(mode="json") if response.content else None
    result["sources"] = [source.model_dump(mode="json") for source in response.sources]
    return {"mode": "local-db" if local_db else "fixture", "real_llm_calls": 0, **result}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-db", action="store_true", help="Read existing local DB/index; use local MedCPT")
    parser.add_argument("--query", default="public biomedical evidence")
    parser.add_argument("--fixture-server", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.fixture_server:
        import anyio
        from evidenceops.mcp_server import serve
        anyio.run(serve, fixture_executor())
        return
    print(json.dumps(run_demo(args.query, local_db=args.local_db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

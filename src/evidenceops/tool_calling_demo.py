"""Offline M10.1 demo: real adapter/protocol, fake HTTP and biomedical backends."""

import argparse
from contextlib import closing
import json
from uuid import UUID

import httpx

from evidenceops.biomedical import BiomedicalDocument
from evidenceops.chunking import build_retrievable_unit
from evidenceops.deepseek_tools import DeepSeekToolCaller
from evidenceops.generation import GenerationError
from evidenceops.observability import configure_logging
from evidenceops.rag import ABSTENTION_ANSWER
from evidenceops.retrieval import RetrievalResult
from evidenceops.tool_calling import ToolCallingService
from evidenceops.tools import ToolCallingError, ToolExecutor

PUBLICATION_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
SCENARIOS = ("search", "publication", "empty", "not-found", "invalid", "unknown", "second-round", "backend-error")


def run_demo(scenario: str) -> dict:
    """Always MockTransport: no live mode, key, model download or database."""
    document = BiomedicalDocument(source="pubmed", source_id="demo-fixture", title="Synthetic fixture",
        abstract="Synthetic abstract for demonstrating the contract; no clinical claims.",
        authors=["Fixture Group"], journal=None, doi=None, publication_year=None, source_url=None)
    unit = build_retrievable_unit(document, publication_id=PUBLICATION_ID)
    requested_tool = "get_publication" if scenario in {"publication", "not-found"} else "search_evidence"
    arguments = ({"publication_id": str(PUBLICATION_ID)} if requested_tool == "get_publication"
                 else {"query": "Discover local publications", "top_k": 2})
    if scenario == "invalid":
        arguments["top_k"] = 6
    if scenario == "unknown":
        requested_tool = "ingest_publication"
    request_count = 0

    def transport(request):
        nonlocal request_count
        request_count += 1
        if request_count == 1 or scenario == "second-round":
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "demo_call_1", "type": "function", "function": {
                    "name": requested_tool, "arguments": json.dumps(arguments)}}]}
            reason = "tool_calls"
        else:
            tool_result = json.loads(json.loads(request.content)["messages"][-1]["content"])
            absent = tool_result["status"] == "error" or tool_result["data"].get("items") == []
            answer = ABSTENTION_ANSWER if absent else (
                "Se encontró una publicación candidata; no se consultó su abstract [S1]."
                if requested_tool == "search_evidence" else "Se consultó el abstract de una publicación local [S1].")
            message = {"role": "assistant", "content": json.dumps({"answer": answer, "limitations": []})}
            reason = "stop"
        return httpx.Response(200, json={"choices": [{"finish_reason": reason, "message": message}]})

    def retrieve(**arguments):
        if scenario == "backend-error":
            raise RuntimeError("Simulated backend error")
        return [] if scenario == "empty" else [RetrievalResult(unit, 1.0)]

    executor = ToolExecutor(retrieve, lambda _: None if scenario == "not-found" else document)
    with closing(DeepSeekToolCaller("offline-placeholder", transport=httpx.MockTransport(transport))) as model:
        try:
            response = ToolCallingService(model, executor).run("Discover local publications")
        except (ToolCallingError, GenerationError) as exc:
            return {"scenario": scenario, "status": "error", "code":
                    exc.code if isinstance(exc, ToolCallingError) else exc.cause.value,
                    "simulated_requests": request_count}
    return {"scenario": scenario, "status": "ok", "answer": response.answer,
            "limitations": response.limitations,
            "sources": [source.model_dump(mode="json") for source in response.sources],
            "tool_result": response.tool_result.payload() if response.tool_result else None,
            "simulated_requests": request_count}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="search")
    parser.add_argument("--logs", action="store_true", help="Enable safe JSON events")
    args = parser.parse_args()
    if args.logs:
        configure_logging()
    print(json.dumps(run_demo(args.scenario), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""M10.2 offline demo: the real graph, adapter and executor over synthetic data."""

import argparse
from contextlib import closing
from dataclasses import asdict
import json

import httpx

from evidenceops.agent import AgentService
from evidenceops.biomedical import BiomedicalDocument
from evidenceops.chunking import build_retrievable_unit
from evidenceops.deepseek_tools import DeepSeekToolCaller
from evidenceops.observability import configure_logging
from evidenceops.rag import ABSTENTION_ANSWER
from evidenceops.retrieval import RetrievalResult
from evidenceops.tool_calling_demo import PUBLICATION_ID
from evidenceops.tools import ToolExecutor

SCENARIOS = ("evidence", "empty", "not-found", "no-abstract", "repeat", "budget", "exhausted",
             "backend-error", "model-error", "timeout", "invalid-citations")


def run_demo(scenario: str) -> dict:
    if scenario not in SCENARIOS:
        raise ValueError("Unknown offline scenario")
    document = BiomedicalDocument(source="pubmed", source_id="demo-fixture", title="Synthetic fixture",
        abstract=None if scenario == "no-abstract" else "Synthetic abstract. No clinical claims.",
        authors=["Fixture Group"], journal=None, doi=None, publication_year=None, source_url=None)
    unit = build_retrievable_unit(document, publication_id=PUBLICATION_ID)
    requests = 0

    def transport(request):
        nonlocal requests
        requests += 1
        body = json.loads(request.content)
        if scenario == "timeout":
            raise httpx.ReadTimeout("Simulated timeout")
        if scenario == "model-error":
            return httpx.Response(503)
        if requests == 1 or scenario in {"repeat", "exhausted"} or (scenario == "budget" and requests < 4):
            name, arguments = "search_evidence", {"query": "Discover fixtures" if scenario == "repeat" else f"Fixtures {requests}"}
        elif requests == 2 and scenario not in {"empty", "budget"}:
            # Read the ID actually returned through the real serialization path.
            result = json.loads(body["messages"][-1]["content"])
            name = "get_publication"
            arguments = {"publication_id": result["data"]["items"][0]["publication_id"]}
        else:
            answer = ABSTENTION_ANSWER if scenario in {"empty", "not-found", "no-abstract"} else (
                "Se encontró una publicación candidata [S1]." if scenario == "budget" else
                "Se consultó un abstract sintético [S1].")
            if scenario == "invalid-citations":
                answer = "Referencia no entregada [S99]."
            return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"answer": answer, "limitations": []})}}]})
        return httpx.Response(200, json={"choices": [{"finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": None, "tool_calls": [{"id": f"demo_{requests}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}]}}]})

    def retrieve(**arguments):
        if scenario == "backend-error":
            raise RuntimeError("Simulated backend failure")
        return [] if scenario == "empty" else [RetrievalResult(unit, 1.0)]

    with closing(DeepSeekToolCaller("offline-placeholder", transport=httpx.MockTransport(transport))) as model:
        response = AgentService(model, ToolExecutor(retrieve, lambda _: None if scenario == "not-found" else document)).run(
            "Discover and read synthetic public evidence")
    output = asdict(response)
    output["content"] = response.content.model_dump(mode="json") if response.content else None
    output["sources"] = [source.model_dump(mode="json") for source in response.sources]
    return {"scenario": scenario, **output, "simulated_requests": requests}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="evidence")
    parser.add_argument("--logs", action="store_true")
    args = parser.parse_args()
    if args.logs:
        configure_logging()
    print(json.dumps(run_demo(args.scenario), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""MCP v2 contracts and real stdio; deterministic data/model, no inference."""

import json
import sys
from unittest.mock import Mock

import anyio
from mcp import Client, StdioServerParameters
from mcp.types import CallToolResult, REQUEST_TIMEOUT
from mcp.shared.exceptions import MCPError
import pytest

from evidenceops.agent import AgentService
from evidenceops.mcp_client import MCPToolExecutor, connect_mcp_tools
from evidenceops.mcp_demo import DemoModel, fixture_executor, run_demo
from evidenceops.mcp_server import create_mcp_server
from evidenceops.tools import TOOL_DEFINITIONS, ToolCallingError, ToolResult
from test_agent import answer, proposal, scripted
from test_tools import PUBLICATION_ID, call


def fixture_parameters():
    return StdioServerParameters(command=sys.executable,
        args=["-m", "evidenceops.mcp_demo", "--fixture-server"])


def test_discovery_and_execution_over_sdk():
    async def check():
        async with Client(create_mcp_server(fixture_executor())) as client:
            catalog = (await client.list_tools()).tools
            assert {t.name for t in catalog} == {d.name for d in TOOL_DEFINITIONS}
            for tool in catalog:
                definition = next(d for d in TOOL_DEFINITIONS if d.name == tool.name)
                assert tool.input_schema == definition.arguments.model_json_schema()
                assert tool.output_schema == ToolResult.model_json_schema()
                assert tool.annotations.read_only_hint
            assert client.server_capabilities.resources is None
            assert client.server_capabilities.prompts is None
            search = await client.call_tool("search_evidence", {"query": "fixture"})
            assert not search.is_error
            payload = search.structured_content
            assert "abstract" not in payload["data"]["items"][0]
            assert json.loads(search.content[0].text) == payload
            read = await client.call_tool("get_publication", {"publication_id": str(PUBLICATION_ID)})
            assert read.structured_content["data"]["abstract"].startswith("Synthetic")
            missing = await client.call_tool("get_publication", {"publication_id": "00000000-0000-0000-0000-000000000000"})
            assert not missing.is_error  # recoverable domain result, same as direct execution
            assert missing.structured_content["error"]["code"] == "publication_not_found"
    anyio.run(check)


@pytest.mark.parametrize("name,args,code", [
    ("unknown", {}, "unknown_tool"),
    ("search_evidence", {}, "invalid_arguments"),
    ("search_evidence", {"query": " "}, "invalid_arguments"),
    ("search_evidence", {"query": "x", "top_k": True}, "invalid_arguments"),
    ("search_evidence", {"query": "x", "top_k": 6}, "invalid_arguments"),
    ("search_evidence", {"query": "x", "extra": "private-input"}, "invalid_arguments"),
    ("search_evidence", {"query": "x" * 4001}, "invalid_arguments"),
    ("get_publication", {"publication_id": "private-input"}, "invalid_arguments"),
])
def test_server_rejects_invalid_inputs_safely(name, args, code):
    async def check():
        executor = fixture_executor()
        executor._retrieve = Mock(side_effect=AssertionError("must not run"))
        executor._lookup = Mock(side_effect=AssertionError("must not run"))
        async with Client(create_mcp_server(executor)) as client:
            result = await client.call_tool(name, args)
            assert result.is_error and result.structured_content == {"code": code}
            assert "private-input" not in str(result)
        executor._retrieve.assert_not_called()
        executor._lookup.assert_not_called()
    anyio.run(check)


def test_backend_failure_is_sanitized_over_mcp():
    async def check():
        executor = fixture_executor()
        executor._retrieve = Mock(side_effect=RuntimeError("password-secret SQL private abstract"))
        async with Client(create_mcp_server(executor)) as client:
            result = await client.call_tool("search_evidence", {"query": "x"})
            assert result.is_error and result.structured_content == {"code": "backend_error"}
            assert "password-secret" not in str(result)
    anyio.run(check)


def test_stdio_discovery_agent_roundtrip_and_correlation():
    with connect_mcp_tools(fixture_parameters()) as executor:
        result = executor.execute(call())
        assert result.call_id == "call_1" and result.sources()[0].publication_id == PUBLICATION_ID
        response = AgentService(DemoModel("fixture"), executor).run("fixture")
        assert response.status == "answered"
        assert (response.llm_calls, response.tool_calls, response.steps) == (3, 2, 6)
        assert response.sources[0].detail_level == "abstract"
        assert response.sources[0].citation_id == "S1"


@pytest.mark.parametrize("turns,reason,tools", [
    ([proposal(), proposal(identifier="repeat")], "repeated_call", 1),
    ([proposal(arguments={"top_k": 6, "query": "x"})], "invalid_arguments", 0),
    ([proposal(), answer("Invented [S99].")], "invalid_citations", 1),
    ([*(proposal(arguments={"query": str(i)}, identifier=f"c{i}") for i in range(4))], "tool_call_limit", 3),
])
def test_agent_limits_remain_effective_through_mcp(turns, reason, tools):
    with connect_mcp_tools(fixture_parameters()) as executor:
        response = AgentService(scripted(*turns), executor).run("fixture")
    assert response.termination_reason == reason
    assert response.content is None and response.tool_calls == tools
    assert response.llm_calls <= 4 and response.steps <= 8


def test_offline_demo():
    result = run_demo("fixture")
    assert result["real_llm_calls"] == 0 and result["status"] == "answered"


@pytest.mark.parametrize("payload,error,code", [
    (None, False, "mcp_contract_error"),
    ({"code": "backend_error"}, True, "backend_error"),
    ({"code": "private arbitrary message"}, True, "mcp_contract_error"),
    ({"code": []}, True, "mcp_contract_error"),
    ({"arbitrary": "data"}, False, "mcp_contract_error"),
    ({"oversized": "x" * 20001}, False, "result_too_large"),
])
def test_client_validates_remote_results(payload, error, code):
    portal = Mock()
    portal.call.return_value = CallToolResult(content=[], structured_content=payload, is_error=error)
    executor = MCPToolExecutor(portal, Mock())
    with pytest.raises(ToolCallingError) as caught:
        executor.execute(call())
    assert caught.value.code == code
    assert portal.call.call_count == 1


@pytest.mark.parametrize("exception,code", [(TimeoutError(), "tool_timeout"),
                                           (OSError("private"), "mcp_connection_error"),
                                           (MCPError(code=REQUEST_TIMEOUT, message="private"), "tool_timeout"),
                                           (RuntimeError("bad schema"), "mcp_contract_error")])
def test_client_controls_transport_errors_without_retry(exception, code):
    portal = Mock()
    portal.call.side_effect = exception
    with pytest.raises(ToolCallingError) as caught:
        MCPToolExecutor(portal, Mock()).execute(call())
    assert caught.value.code == code and portal.call.call_count == 1


def test_subprocess_exit_is_controlled():
    with pytest.raises(ToolCallingError, match="mcp_connection_error"):
        with connect_mcp_tools(StdioServerParameters(command=sys.executable, args=["-c", "pass"])):
            pytest.fail("dead subprocess must not yield an executor")


def test_incompatible_catalog_is_rejected_before_agent(monkeypatch):
    monkeypatch.setattr("evidenceops.mcp_client.tool_catalog", lambda: [])
    with pytest.raises(ToolCallingError, match="mcp_contract_error"):
        with connect_mcp_tools(fixture_parameters()):
            pytest.fail("incompatible catalog must not yield an executor")


def test_real_stdio_timeout_terminates_graph_without_retry(monkeypatch):
    monkeypatch.setattr("evidenceops.mcp_client.TOOL_BUDGET_SECONDS", 0.2)
    script = """import anyio
import time
from evidenceops.mcp_server import serve
from evidenceops.tools import ToolExecutor
def retrieve(**kw):
    time.sleep(1)
    return []
anyio.run(serve, ToolExecutor(retrieve, lambda _: None))
"""
    with connect_mcp_tools(StdioServerParameters(command=sys.executable, args=["-c", script])) as executor:
        model = scripted(proposal(), answer())
        response = AgentService(model, executor).run("fixture")
    assert response.status == "error" and response.termination_reason == "tool_timeout"
    assert response.content is None and response.tool_calls == 1 and response.llm_calls == 1
    assert model.decide.call_count == 1


def test_context_preserves_caller_exception():
    with pytest.raises(ValueError, match="caller failure"):
        with connect_mcp_tools(fixture_parameters()):
            raise ValueError("caller failure")


def test_client_rejects_wrong_tool_and_publication_identity():
    portal = Mock()
    detail = fixture_executor().execute(call("get_publication", {"publication_id": str(PUBLICATION_ID)}))
    portal.call.return_value = CallToolResult(content=[], structured_content=detail.payload())
    executor = MCPToolExecutor(portal, Mock())
    with pytest.raises(ToolCallingError, match="mcp_contract_error"):
        executor.execute(call())
    with pytest.raises(ToolCallingError, match="mcp_contract_error"):
        executor.execute(call("get_publication", {"publication_id": "00000000-0000-0000-0000-000000000000"}))

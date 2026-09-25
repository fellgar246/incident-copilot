from __future__ import annotations

from incident_contracts.enums import ToolClass
from incident_contracts.gateway import (
    GATEWAY_SEARCH_ENABLED,
    GATEWAY_TOOL_NAMES,
    MAX_GATEWAY_TOOLS,
    TOOL_CALLS_METRIC,
    WEB_SEARCH_ENABLED,
    gateway_tools,
    load_tool_schema,
    tool_called_schema,
)
from jsonschema import Draft202012Validator


def test_catalog_is_read_only_and_under_the_cap() -> None:
    tools = gateway_tools()
    assert GATEWAY_SEARCH_ENABLED is False
    assert WEB_SEARCH_ENABLED is False
    assert len(tools) < 10
    assert len(tools) <= MAX_GATEWAY_TOOLS
    assert tuple(tool.name for tool in tools) == GATEWAY_TOOL_NAMES
    assert TOOL_CALLS_METRIC == "tool_calls"
    for tool in tools:
        assert tool.tool_class is ToolClass.READ_ONLY
        assert tool.timeout_seconds == 3.0
        assert tool.iam_scope
        Draft202012Validator.check_schema(tool.input_schema)
        Draft202012Validator.check_schema(tool.output_schema)
        assert tool.name != "execute_remediation"
    assert "search_runbooks" in {tool.name for tool in tools}


def test_evidence_inputs_reject_free_form_queries() -> None:
    logs = load_tool_schema("query_logs.input.v1.json")
    assert "query" not in logs["properties"]
    assert logs["additionalProperties"] is False
    metrics = load_tool_schema("query_metrics.input.v1.json")
    assert set(metrics["properties"]["metric"]["enum"]) == {
        "error_rate",
        "request_count",
        "latency_p95",
        "throttles",
        "duration",
        "custom_health",
    }


def test_tool_called_payload_has_no_argument_slot() -> None:
    schema = tool_called_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"tool", "ok", "latency_ms", "truncated", "error"}
    assert "args" not in schema["properties"]
    assert "prompt" not in schema["properties"]

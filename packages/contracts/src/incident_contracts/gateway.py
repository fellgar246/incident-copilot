"""Versioned tool catalog exposed to the agent. Search and web search stay off."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from incident_contracts.enums import ToolClass

TOOL_SCHEMA_VERSION = "1"
MAX_GATEWAY_TOOLS = 9
GATEWAY_SEARCH_ENABLED = False
WEB_SEARCH_ENABLED = False
TOOL_CALLS_METRIC = "tool_calls"

GATEWAY_TOOL_NAMES: tuple[str, ...] = (
    "get_incident",
    "query_logs",
    "query_metrics",
    "get_recent_deployments",
    "search_runbooks",
    "request_remediation",
)

# execute_remediation is invoked by the API after a grant. It is not a gateway tool.
AGENT_FORBIDDEN_TOOLS: frozenset[str] = frozenset({"execute_remediation"})

_SCHEMA_DIR = "schemas/tools"


class ToolCalledV1(BaseModel):
    """Timeline payload for one tool invocation. Raw arguments are not stored."""

    model_config = ConfigDict(extra="forbid")

    tool: Literal[
        "get_incident",
        "query_logs",
        "query_metrics",
        "get_recent_deployments",
        "search_runbooks",
        "request_remediation",
    ]
    ok: bool
    latency_ms: int = Field(ge=0)
    truncated: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class GatewayTool:
    """One tool the agent may discover. IAM is a documented scope, not a SDK."""

    name: str
    description: str
    tool_class: ToolClass
    timeout_seconds: float
    iam_scope: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    def __post_init__(self) -> None:
        if self.name in AGENT_FORBIDDEN_TOOLS or self.tool_class is ToolClass.DESTRUCTIVE:
            raise ValueError(f"{self.name} is not available to the agent")
        if self.tool_class is ToolClass.SAFE_WRITE and self.name != "request_remediation":
            raise ValueError(f"{self.name} is not a request-only safe write")
        if self.tool_class is ToolClass.READ_ONLY and self.name == "request_remediation":
            raise ValueError("request_remediation requires human approval")
        if self.timeout_seconds <= 0:
            raise ValueError(f"{self.name} timeout must be > 0")


def load_tool_schema(name: str) -> dict[str, Any]:
    """Load a published v1 JSON Schema document from the contracts package."""
    resource = files("incident_contracts").joinpath(f"{_SCHEMA_DIR}/{name}")
    loaded: Any = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"{name} must be a JSON object")
    return loaded


def tool_called_schema() -> dict[str, Any]:
    return load_tool_schema("tool_called.v1.json")


def gateway_tools() -> tuple[GatewayTool, ...]:
    """Return the only tools the agent may discover. execute_remediation is absent."""
    if GATEWAY_SEARCH_ENABLED or WEB_SEARCH_ENABLED:
        raise RuntimeError("gateway search and web search must stay disabled")
    tools = (
        GatewayTool(
            name="get_incident",
            description="Load the incident under investigation without secrets or prompts.",
            tool_class=ToolClass.READ_ONLY,
            timeout_seconds=3.0,
            iam_scope="dynamodb:GetItem on the incidents table",
            input_schema=load_tool_schema("get_incident.input.v1.json"),
            output_schema=load_tool_schema("get_incident.output.v1.json"),
        ),
        GatewayTool(
            name="query_logs",
            description="Read recent allowlisted logs for one demo service.",
            tool_class=ToolClass.READ_ONLY,
            timeout_seconds=3.0,
            iam_scope=(
                "logs:FilterLogEvents, logs:GetLogEvents, logs:DescribeLogStreams "
                "on demo log groups"
            ),
            input_schema=load_tool_schema("query_logs.input.v1.json"),
            output_schema=load_tool_schema("query_logs.output.v1.json"),
        ),
        GatewayTool(
            name="query_metrics",
            description="Read one allowlisted metric for one demo service.",
            tool_class=ToolClass.READ_ONLY,
            timeout_seconds=3.0,
            iam_scope=(
                "cloudwatch:GetMetricStatistics and cloudwatch:ListMetrics "
                "conditioned on namespace AIIncidentCopilot/Demo"
            ),
            input_schema=load_tool_schema("query_metrics.input.v1.json"),
            output_schema=load_tool_schema("query_metrics.output.v1.json"),
        ),
        GatewayTool(
            name="get_recent_deployments",
            description="Read recent deployments for one demo service.",
            tool_class=ToolClass.READ_ONLY,
            timeout_seconds=3.0,
            iam_scope="dynamodb:Query on the deployments table",
            input_schema=load_tool_schema("get_recent_deployments.input.v1.json"),
            output_schema=load_tool_schema("get_recent_deployments.output.v1.json"),
        ),
        GatewayTool(
            name="search_runbooks",
            description="Retrieve operational documents for one demo service.",
            tool_class=ToolClass.READ_ONLY,
            timeout_seconds=3.0,
            iam_scope="bedrock:Retrieve and s3:GetObject on the corpus bucket",
            input_schema=load_tool_schema("search_runbooks.input.v1.json"),
            output_schema=load_tool_schema("search_runbooks.output.v1.json"),
        ),
        GatewayTool(
            name="request_remediation",
            description=(
                "Record a safe-write proposal and wait for a human. Does not change any resource."
            ),
            tool_class=ToolClass.SAFE_WRITE,
            timeout_seconds=3.0,
            iam_scope="remediation-tool-role: no execute; proposal write on the incident item only",
            input_schema=load_tool_schema("request_remediation.input.v1.json"),
            output_schema=load_tool_schema("request_remediation.output.v1.json"),
        ),
    )
    if len(tools) > MAX_GATEWAY_TOOLS:
        raise RuntimeError("gateway tool catalog exceeds the indexing cap")
    names = tuple(tool.name for tool in tools)
    if names != GATEWAY_TOOL_NAMES:
        raise RuntimeError("gateway catalog drifted from the authorized names")
    return tools


def gateway_tool(name: str) -> GatewayTool:
    for tool in gateway_tools():
        if tool.name == name:
            return tool
    raise KeyError(name)

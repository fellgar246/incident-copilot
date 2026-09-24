"""Build and submit the gateway catalog. Search and unknown tools are refused."""

from __future__ import annotations

import os
from typing import Any

from incident_contracts.gateway import (
    GATEWAY_SEARCH_ENABLED,
    GATEWAY_TOOL_NAMES,
    WEB_SEARCH_ENABLED,
    gateway_tools,
)

SEARCH_FLAGS = ("GATEWAY_SEARCH_ENABLED", "WEB_SEARCH_ENABLED")


def registration_document(environ: Any | None = None) -> dict[str, Any]:
    """Target document for the four authorized tools. Search stays disabled."""
    _refuse_search(os.environ if environ is None else environ)
    tools = []
    for tool in gateway_tools():
        if tool.name not in GATEWAY_TOOL_NAMES:
            raise RuntimeError(f"refusing to register {tool.name}")
        tools.append(
            {
                "name": tool.name,
                "description": tool.description,
                "tool_class": tool.tool_class.value,
                "timeout_seconds": tool.timeout_seconds,
                "iam_scope": tool.iam_scope,
                "input_schema": tool.input_schema,
                "output_schema": tool.output_schema,
            }
        )
    return {
        "search_enabled": False,
        "web_search_enabled": False,
        "tool_count": len(tools),
        "tools": tools,
    }


def apply_registration(client: Any, document: dict[str, Any]) -> dict[str, Any]:
    """Submit the catalog. The client is never asked to enable search."""
    if document["search_enabled"] or document["web_search_enabled"]:
        raise RuntimeError("refusing to enable gateway search or web search")
    names = [item["name"] for item in document["tools"]]
    if names != list(GATEWAY_TOOL_NAMES):
        raise RuntimeError("refusing to register a tool outside the catalog")
    response: Any = client.create_gateway(
        name="incident-tools",
        protocolType="MCP",
        authorizerType="AWS_IAM",
    )
    for tool in document["tools"]:
        client.create_gateway_target(
            gatewayIdentifier=response["gatewayId"],
            name=tool["name"],
            targetConfiguration={
                "mcp": {"lambda": {"toolSchema": {"inputSchema": tool["input_schema"]}}}
            },
        )
    return {"gatewayId": response.get("gatewayId"), "tools": names}


def _refuse_search(environ: Any) -> None:
    if GATEWAY_SEARCH_ENABLED or WEB_SEARCH_ENABLED:
        raise RuntimeError("gateway search and web search are disabled in the catalog")
    for flag in SEARCH_FLAGS:
        if str(environ.get(flag, "false")).strip().lower() in {"1", "true", "yes"}:
            raise RuntimeError(f"refusing to enable {flag}")

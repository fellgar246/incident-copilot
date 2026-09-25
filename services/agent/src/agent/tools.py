"""Gateway-backed tool dispatch. Names outside the allowlist are never executed."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Protocol

from incident_contracts.gateway import GATEWAY_TOOL_NAMES
from incident_contracts.models import Incident

from agent.gateway import GatewayClient, GatewayError, ToolCallAudit

ALLOWLIST: frozenset[str] = frozenset(GATEWAY_TOOL_NAMES)

assert "search_runbooks" in ALLOWLIST


class ToolError(RuntimeError):
    """A tool name was rejected or its handler failed closed."""


class LogTool(Protocol):
    def query_logs(
        self,
        payload: Any,
        *,
        now: datetime | None = None,
        calls_used: int | None = None,
    ) -> Any: ...


class MetricTool(Protocol):
    def query_metrics(
        self, payload: Any, *, now: datetime | None = None, calls_used: int | None = None
    ) -> Any: ...


class DeploymentTool(Protocol):
    def get_recent_deployments(
        self, payload: Any, *, now: datetime | None = None, calls_used: int | None = None
    ) -> Any: ...


class IncidentLookup(Protocol):
    def get(self, incident_id: str) -> Incident: ...


class KnowledgeTool(Protocol):
    def search_runbooks(self, payload: Any, *, rag_calls_used: int = 0) -> Any: ...


class ToolDispatcher:
    """Execute allowlisted read tools. Reject every other name, including ones found in logs."""

    def __init__(
        self,
        *,
        incidents: IncidentLookup,
        logs: LogTool,
        metrics: MetricTool,
        deployments: DeploymentTool,
        knowledge: KnowledgeTool | None = None,
        incident_id: str,
        observed_at: datetime,
        audit: ToolCallAudit,
        agent_run_id: str,
    ) -> None:
        self._incidents = incidents
        self._logs = logs
        self._metrics = metrics
        self._deployments = deployments
        self._knowledge = knowledge if knowledge is not None else _default_knowledge()
        self._incident_id = incident_id
        self._rag_calls_used = 0
        self._observed_at = observed_at
        self._calls_used = 0
        self._gateway = GatewayClient(
            {name: self._bind(name) for name in ALLOWLIST},
            audit=audit,
            incident_id=incident_id,
            agent_run_id=agent_run_id,
        )
        self.invoked = self._gateway.invoked

    def _bind(self, name: str) -> Callable[[dict[str, Any]], Any]:
        def handler(arguments: dict[str, Any]) -> Any:
            return _HANDLERS[name](self, arguments)

        return handler

    def _tool_now(self) -> datetime:
        """Anchor tool windows on the incident clock so fixture samples stay in range."""
        return self._observed_at + timedelta(minutes=15)

    def dispatch(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        calls_used: int,
        rag_calls_used: int = 0,
    ) -> str:
        self._calls_used = calls_used
        self._rag_calls_used = rag_calls_used
        try:
            payload = self._gateway.invoke(name, arguments, calls_used=calls_used)
        except GatewayError as exc:
            raise ToolError(str(exc)) from exc
        return json.dumps(payload, default=str)


def _get_incident(dispatcher: ToolDispatcher, arguments: dict[str, Any]) -> Any:
    del arguments
    incident = dispatcher._incidents.get(dispatcher._incident_id)
    return {
        "tool": "get_incident",
        "tool_class": "READ_ONLY",
        "requires_approval": False,
        "incident_id": incident.incident_id,
        "service": incident.service,
        "alarm_name": incident.alarm_name,
        "severity": incident.severity.value,
        "status": incident.status.value,
        "started_at": incident.started_at.isoformat(),
        "updated_at": incident.updated_at.isoformat(),
        "known_context": {"correlation_id": incident.correlation_id},
        "redacted": True,
        "truncated": False,
        "untrusted": True,
    }


def _query_logs(dispatcher: ToolDispatcher, arguments: dict[str, Any]) -> Any:
    result = dispatcher._logs.query_logs(
        arguments, now=dispatcher._tool_now(), calls_used=dispatcher._calls_used
    )
    return _dump(result)


def _query_metrics(dispatcher: ToolDispatcher, arguments: dict[str, Any]) -> Any:
    result = dispatcher._metrics.query_metrics(
        arguments, now=dispatcher._tool_now(), calls_used=dispatcher._calls_used
    )
    return _dump(result)


def _deployments(dispatcher: ToolDispatcher, arguments: dict[str, Any]) -> Any:
    result = dispatcher._deployments.get_recent_deployments(
        arguments, now=dispatcher._tool_now(), calls_used=dispatcher._calls_used
    )
    return _dump(result)


def _search_runbooks(dispatcher: ToolDispatcher, arguments: dict[str, Any]) -> Any:
    result = dispatcher._knowledge.search_runbooks(
        arguments, rag_calls_used=dispatcher._rag_calls_used
    )
    return _dump(result)


def _default_knowledge() -> KnowledgeTool:
    from knowledge_tool.tools import KnowledgeTools

    return KnowledgeTools()


def _dump(result: Any) -> Any:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return result


_HANDLERS: dict[str, Callable[[ToolDispatcher, dict[str, Any]], Any]] = {
    "get_incident": _get_incident,
    "query_logs": _query_logs,
    "query_metrics": _query_metrics,
    "get_recent_deployments": _deployments,
    "search_runbooks": _search_runbooks,
}

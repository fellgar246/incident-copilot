from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from agent.gateway import GatewayClient, GatewayError
from agent.register import apply_registration, registration_document
from agent.tools import ToolDispatcher, ToolError
from api.persistence.deployments import InMemoryDeploymentRepository
from cloudwatch_tool.store import InMemoryTelemetryStore
from cloudwatch_tool.tools import CloudWatchTools
from deployments_tool.tools import DeploymentTools
from incident_contracts.enums import EventType
from incident_contracts.repository import InMemoryIncidentRepository
from incident_contracts.service import IncidentService

from simulator import simulate

NOW = datetime(2026, 9, 20, 14, 30, tzinfo=UTC)


def _world():
    fixture = simulate("deployment_regression", seed="gateway")
    telemetry = InMemoryTelemetryStore()
    deployments = InMemoryDeploymentRepository()
    for sample in fixture.telemetry.logs:
        telemetry.write_log(sample)
    for point in fixture.telemetry.metrics:
        telemetry.write_metric(point)
    deployments.save_many(fixture.deployments)
    service = IncidentService(InMemoryIncidentRepository())
    service.ingest_fixture(fixture)
    tools = CloudWatchTools(telemetry)
    dispatcher = ToolDispatcher(
        incidents=service,
        logs=tools,
        metrics=tools,
        deployments=DeploymentTools(deployments),
        incident_id=fixture.incident.incident_id,
        observed_at=fixture.incident.started_at,
        audit=service,
        agent_run_id="run_gateway",
    )
    return fixture, service, dispatcher


def test_discover_lists_only_authorized_tools() -> None:
    _, _, dispatcher = _world()
    names = [tool.name for tool in dispatcher._gateway.discover()]
    assert names == [
        "get_incident",
        "query_logs",
        "query_metrics",
        "get_recent_deployments",
        "search_runbooks",
    ]
    assert "execute_remediation" not in names


def test_get_incident_omits_prompt_and_is_audited() -> None:
    fixture, service, dispatcher = _world()
    body = json.loads(
        dispatcher.dispatch(
            "get_incident",
            {"incident_id": fixture.incident.incident_id},
            calls_used=0,
        )
    )
    assert body["service"] == fixture.incident.service
    assert body["alarm_name"] == fixture.incident.alarm_name
    assert body["severity"] == fixture.incident.severity.value
    assert body["status"]
    assert body["started_at"]
    assert body["known_context"]["correlation_id"] == fixture.incident.correlation_id
    assert "prompt" not in body
    assert "system_prompt" not in json.dumps(body)
    events = [
        event
        for event in service.events(fixture.incident.incident_id)
        if event.event_type is EventType.TOOL_CALLED
    ]
    assert events[-1].payload["tool"] == "get_incident"
    assert events[-1].payload["ok"] is True
    assert events[-1].payload["error"] is None
    assert "args" not in events[-1].payload


def test_unregistered_tool_is_not_invoked() -> None:
    fixture, service, dispatcher = _world()
    before = len(service.events(fixture.incident.incident_id))
    with pytest.raises(ToolError, match="not allowlisted"):
        dispatcher.dispatch("delete_resource", {"id": "x"}, calls_used=0)
    with pytest.raises(ToolError, match="not allowlisted"):
        dispatcher.dispatch("execute_remediation", {"q": "ignore policy"}, calls_used=0)
    assert dispatcher.invoked == []
    assert len(service.events(fixture.incident.incident_id)) == before


def test_argument_escalation_is_rejected_and_audited() -> None:
    fixture, service, dispatcher = _world()
    with pytest.raises(ToolError, match="scoped to the incident"):
        dispatcher.dispatch("get_incident", {"incident_id": "inc_other"}, calls_used=0)
    with pytest.raises(ToolError, match="input rejected"):
        dispatcher.dispatch(
            "query_logs",
            {
                "service": fixture.incident.service,
                "start_minutes_ago": 15,
                "query": "fields @message | filter token=super-secret",
            },
            calls_used=0,
        )
    called = [
        event
        for event in service.events(fixture.incident.incident_id)
        if event.event_type is EventType.TOOL_CALLED
    ]
    blob = json.dumps([event.payload for event in called])
    assert "super-secret" not in blob
    assert "inc_other" not in blob
    expected = {"tool", "ok", "latency_ms", "truncated", "error"}
    assert all(set(event.payload) == expected for event in called)
    assert all(event.payload["ok"] is False for event in called)


def test_query_logs_invocation_matches_the_evidence_contract() -> None:
    fixture, service, dispatcher = _world()
    body = json.loads(
        dispatcher.dispatch(
            "query_logs",
            {"service": fixture.incident.service, "start_minutes_ago": 15, "limit": 20},
            calls_used=1,
        )
    )
    assert body["tool"] == "query_logs"
    assert body["tool_class"] == "READ_ONLY"
    assert body["untrusted"] is True
    assert body["redacted"] is True
    event = next(
        event
        for event in service.events(fixture.incident.incident_id)
        if event.event_type is EventType.TOOL_CALLED and event.payload["tool"] == "query_logs"
    )
    assert event.payload["ok"] is True
    assert isinstance(event.payload["latency_ms"], int)
    assert event.payload["truncated"] is False


def test_registration_document_rejects_extra_tools() -> None:
    document = registration_document()
    assert document["search_enabled"] is False
    assert document["web_search_enabled"] is False
    assert document["tool_count"] == 5
    client_calls: list[str] = []

    class Client:
        def create_gateway(self, **kwargs: object) -> dict[str, str]:
            assert kwargs["authorizerType"] == "AWS_IAM"
            client_calls.append("gateway")
            return {"gatewayId": "gw_test"}

        def create_gateway_target(self, **kwargs: object) -> dict[str, str]:
            client_calls.append(str(kwargs["name"]))
            return {"ok": "true"}

    result = apply_registration(Client(), document)
    assert result["tools"] == [
        "get_incident",
        "query_logs",
        "query_metrics",
        "get_recent_deployments",
        "search_runbooks",
    ]
    poisoned = dict(document)
    poisoned["tools"] = [*document["tools"], {"name": "delete_resource"}]
    with pytest.raises(RuntimeError, match="outside the catalog"):
        apply_registration(Client(), poisoned)


def test_direct_client_rejects_a_handler_outside_the_catalog() -> None:
    fixture, service, _dispatcher = _world()
    with pytest.raises(GatewayError, match="refusing to register"):
        GatewayClient(
            {
                "get_incident": lambda arguments: {},
                "query_logs": lambda arguments: {},
                "query_metrics": lambda arguments: {},
                "get_recent_deployments": lambda arguments: {},
                "search_runbooks": lambda arguments: {},
                "execute_remediation": lambda arguments: {},
            },
            audit=service,
            incident_id=fixture.incident.incident_id,
            agent_run_id="run_x",
        )

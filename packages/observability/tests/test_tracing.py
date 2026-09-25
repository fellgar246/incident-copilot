from __future__ import annotations

import json
import logging
from pathlib import Path

from agent.investigate import investigate
from agent.model import ScriptedInvestigator
from agent.runs import InMemoryAgentRunStore
from api.persistence.deployments import InMemoryDeploymentRepository
from cloudwatch_tool.store import InMemoryTelemetryStore
from cloudwatch_tool.tools import CloudWatchTools
from cost_guardrails.envfile import parse_env_file
from cost_guardrails.quotas import load_quotas
from deployments_tool.tools import DeploymentTools
from incident_contracts.enums import ScenarioId
from incident_contracts.repository import InMemoryIncidentRepository
from incident_contracts.service import IncidentService
from observability.logging import JsonLogFormatter, bind_context, clear_context
from observability.tracing import (
    SPAN_INVESTIGATION_START,
    SPAN_LLM_DIAGNOSIS,
    SPAN_LLM_REASONING,
    reconstruct_trace,
    reset_traces,
    tool_span_name,
)

from simulator import simulate


def test_sample_logs_do_not_contain_secrets() -> None:
    access_key = "AKIA" + ("Z" * 16)
    clear_context()
    bind_context(incident_id="inc_scan", correlation_id="cor_scan", approval_id="appr_scan")
    record = logging.LogRecord(
        name="api",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f"Authorization: Bearer live-token key={access_key}",
        args=(),
        exc_info=None,
    )
    record.fields = {"messages": ["full prompt with Bearer live-token"], "ok": True}
    line = JsonLogFormatter().format(record)
    assert "live-token" not in line
    assert access_key not in line
    assert "full prompt" not in line
    payload = json.loads(line)
    assert payload["incident_id"] == "inc_scan"
    assert payload["approval_id"] == "appr_scan"
    assert payload["messages"] == "[REDACTED]"
    clear_context()


def test_fixture_a_reconstructs_tool_spans() -> None:
    reset_traces()
    fixture = simulate(ScenarioId.DEPLOYMENT_REGRESSION, seed="trace")
    telemetry = InMemoryTelemetryStore()
    deployments = InMemoryDeploymentRepository()
    for sample in fixture.telemetry.logs:
        telemetry.write_log(sample)
    for point in fixture.telemetry.metrics:
        telemetry.write_metric(point)
    deployments.save_many(fixture.deployments)
    repository = InMemoryIncidentRepository()
    service = IncidentService(repository)
    incident = service.ingest_fixture(fixture)
    root = Path(__file__).resolve().parents[3]
    quotas = load_quotas(parse_env_file(root / ".env.example"))
    record = investigate(
        incident_id=incident.incident_id,
        correlation_id=incident.correlation_id,
        idempotency_key="trace-1",
        service=service,
        runs=InMemoryAgentRunStore(),
        quotas=quotas,
        model=ScriptedInvestigator(),
        logs=CloudWatchTools(telemetry),
        metrics=CloudWatchTools(telemetry),
        deployments=DeploymentTools(deployments),
    )
    tree = reconstruct_trace(incident.incident_id)
    names = _names(tree["spans"])
    assert SPAN_INVESTIGATION_START in names
    assert SPAN_LLM_REASONING in names
    assert SPAN_LLM_DIAGNOSIS in names
    for tool in ("query_logs", "query_metrics", "search_runbooks"):
        assert tool_span_name(tool) in names
    assert record.estimated_cost_usd >= 0
    assert record.incident_id == tree["incident_id"]


def _names(nodes: object) -> set[str]:
    found: set[str] = set()
    if not isinstance(nodes, list):
        return found
    for node in nodes:
        if not isinstance(node, dict):
            continue
        name = node.get("name")
        if isinstance(name, str):
            found.add(name)
        found.update(_names(node.get("children")))
    return found

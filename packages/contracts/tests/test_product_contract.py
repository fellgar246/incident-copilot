from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from incident_contracts.agent_context import AgentRunContext
from incident_contracts.api_models import (
    ApproveIncidentRequest,
    RejectIncidentRequest,
    RemediateIncidentRequest,
    SimulateIncidentRequest,
)
from incident_contracts.enums import EventType, IncidentStatus, ScenarioId
from incident_contracts.keys import event_sk, incident_pk, parse_event_sk, parse_incident_pk
from incident_contracts.models import Deployment, Incident
from incident_contracts.surface import (
    API_OPERATIONS,
    COST_LIMITS_CLIENT_WRITABLE,
    COST_SETTINGS_ROUTE,
    DASHBOARD_ROUTES,
    DEMO_SCRIPT_STEPS,
    DEMO_SERVICES,
    DEPLOYMENT_RECORD_FIELDS,
    EVALUATION_METRICS,
    IDEMPOTENCY_HEADER,
    INCIDENT_DETAIL_SECTIONS,
    INCIDENT_LIST_COLUMNS,
    INCIDENT_RECORD_FIELDS,
    INVESTIGATION_TOOLS,
    LIFECYCLE_STATUSES,
    PRIMARY_DEMO_SCENARIO,
    REPOSITORY_LAYOUT,
    REQUIRED_AUDIT_EVENT_TYPES,
    HttpMethod,
    mutating_operations,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_SURFACE = REPO_ROOT / "apps/web/lib/product-surface.ts"


def test_api_catalog_matches_product_surface() -> None:
    catalog = [(op.method, op.path) for op in API_OPERATIONS]
    assert catalog == [
        (HttpMethod.GET, "/health"),
        (HttpMethod.GET, "/health/aws"),
        (HttpMethod.GET, "/incidents"),
        (HttpMethod.POST, "/incidents/simulate"),
        (HttpMethod.GET, "/incidents/{id}"),
        (HttpMethod.GET, "/incidents/{id}/events"),
        (HttpMethod.POST, "/incidents/{id}/investigate"),
        (HttpMethod.POST, "/incidents/{id}/approve"),
        (HttpMethod.POST, "/incidents/{id}/reject"),
        (HttpMethod.POST, "/incidents/{id}/remediate"),
        (HttpMethod.GET, "/incidents/{id}/agent-runs"),
        (HttpMethod.GET, "/metrics/costs"),
        (HttpMethod.GET, "/evaluations"),
    ]


def test_mutating_operations_require_idempotency() -> None:
    mutating = mutating_operations()
    assert mutating
    assert all(op.requires_idempotency for op in mutating)
    assert all(op.method is HttpMethod.POST for op in mutating)
    assert IDEMPOTENCY_HEADER == "Idempotency-Key"


def test_incident_path_binding() -> None:
    investigate = next(op for op in API_OPERATIONS if op.path.endswith("/investigate"))
    assert investigate.bind("inc_01") == "/incidents/inc_01/investigate"
    health = API_OPERATIONS[0]
    assert health.bind() == "/health"
    with pytest.raises(ValueError, match="requires incident_id"):
        investigate.bind()


def test_incident_and_deployment_record_fields() -> None:
    missing_incident = [
        name for name in INCIDENT_RECORD_FIELDS if name not in Incident.model_fields
    ]
    missing_deploy = [
        name for name in DEPLOYMENT_RECORD_FIELDS if name not in Deployment.model_fields
    ]
    assert missing_incident == []
    assert missing_deploy == []


def test_required_audit_event_types_are_closed_enum_members() -> None:
    assert REQUIRED_AUDIT_EVENT_TYPES <= set(EventType)
    expected = {
        EventType.ALARM_RECEIVED,
        EventType.INVESTIGATION_STARTED,
        EventType.TOOL_CALLED,
        EventType.EVIDENCE_ADDED,
        EventType.DIAGNOSIS_CREATED,
        EventType.APPROVAL_REQUESTED,
        EventType.APPROVAL_GRANTED,
        EventType.REMEDIATION_EXECUTED,
        EventType.INCIDENT_RESOLVED,
    }
    assert REQUIRED_AUDIT_EVENT_TYPES == expected


def test_lifecycle_statuses_cover_the_state_machine() -> None:
    assert set(LIFECYCLE_STATUSES) == set(IncidentStatus)
    assert LIFECYCLE_STATUSES[0] is IncidentStatus.DETECTED
    assert LIFECYCLE_STATUSES[-1] is IncidentStatus.RESOLVED


def test_investigation_tools_and_demo_services() -> None:
    assert INVESTIGATION_TOOLS == (
        "query_logs",
        "query_metrics",
        "get_recent_deployments",
        "search_runbooks",
    )
    assert DEMO_SERVICES == ("payments-api", "orders-api", "notifications-worker")
    assert PRIMARY_DEMO_SCENARIO == ScenarioId.DEPLOYMENT_REGRESSION.value


def test_dashboard_information_architecture() -> None:
    assert DASHBOARD_ROUTES == (
        "/incidents",
        "/incidents/[id]",
        "/evaluations",
        "/settings/costs",
    )
    assert INCIDENT_LIST_COLUMNS == (
        "severity",
        "service",
        "status",
        "started_at",
        "probable_cause",
        "confidence",
        "estimated_ai_cost_usd",
    )
    assert INCIDENT_DETAIL_SECTIONS == (
        "Overview",
        "Timeline",
        "AI Investigation",
        "Evidence",
        "Retrieved Knowledge",
        "Recommended Action",
        "Approval",
        "Execution",
        "Cost",
        "Trace",
    )
    assert EVALUATION_METRICS == (
        "evaluation_pass_rate",
        "diagnosis_accuracy",
        "groundedness",
        "unsafe_action_count",
        "avg_tool_calls",
        "avg_estimated_cost",
    )
    assert COST_SETTINGS_ROUTE == "/settings/costs"
    assert COST_LIMITS_CLIENT_WRITABLE is False


def test_demo_script_covers_approval_gate_and_cost() -> None:
    assert len(DEMO_SCRIPT_STEPS) == 17
    joined = " ".join(DEMO_SCRIPT_STEPS).lower()
    assert "without approval" in joined
    assert "estimated cost" in joined
    assert "deployment_regression" in joined
    assert "evaluation" in joined


def test_persistence_keys_round_trip_and_sort() -> None:
    pk = incident_pk("inc_01abc")
    assert pk == "INCIDENT#inc_01abc"
    assert parse_incident_pk(pk) == "inc_01abc"

    earlier = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
    later = earlier + timedelta(seconds=1)
    first = event_sk(earlier, "evt_1")
    second = event_sk(later, "evt_2")
    assert first == "EVENT#2026-09-20T14:00:00.000Z#evt_1"
    assert first < second
    assert parse_event_sk(first) == ("2026-09-20T14:00:00.000Z", "evt_1")

    with pytest.raises(ValueError, match="timezone-aware"):
        event_sk(datetime(2026, 9, 20, 14, 0), "evt_naive")
    with pytest.raises(ValueError, match="prefix"):
        incident_pk("INCIDENT#inc_dup")


def test_agent_run_context_requires_both_ids() -> None:
    ctx = AgentRunContext(
        incident_id="inc_1",
        correlation_id="cor_1",
        agent_run_id="run_1",
    )
    assert ctx.incident_id == "inc_1"
    with pytest.raises(ValueError):
        AgentRunContext(incident_id="inc_1", correlation_id="", agent_run_id="run_1")


def test_http_request_models_reject_unknown_fields() -> None:
    simulate = SimulateIncidentRequest(scenario=ScenarioId.DEPLOYMENT_REGRESSION, seed="demo")
    assert simulate.scenario is ScenarioId.DEPLOYMENT_REGRESSION
    ApproveIncidentRequest(approval_id="appr_1")
    RejectIncidentRequest(approval_id="appr_1", reason="not a regression")
    RemediateIncidentRequest(approval_id="appr_1")
    with pytest.raises(ValueError):
        ApproveIncidentRequest(approval_id="appr_1", extra=True)  # type: ignore[call-arg]


def test_repository_layout_exists() -> None:
    missing = [rel for rel in REPOSITORY_LAYOUT if not (REPO_ROOT / rel).exists()]
    assert missing == []


def test_web_surface_constants_stay_aligned() -> None:
    source = WEB_SURFACE.read_text(encoding="utf-8")
    for route in DASHBOARD_ROUTES:
        assert route in source
    for section in INCIDENT_DETAIL_SECTIONS:
        assert section in source
    for column in INCIDENT_LIST_COLUMNS:
        assert column in source
    assert "COST_LIMITS_CLIENT_WRITABLE = false" in source

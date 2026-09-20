"""Product surface: HTTP API, dashboard IA, demo services, and audit events.

This module is the shared contract later slices implement. It does not serve HTTP
or render UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from incident_contracts.enums import EventType, IncidentStatus


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"


@dataclass(frozen=True)
class ApiOperation:
    method: HttpMethod
    path: str
    mutating: bool
    requires_idempotency: bool

    def bind(self, incident_id: str | None = None) -> str:
        if "{id}" in self.path:
            if not incident_id:
                raise ValueError(f"{self.path} requires incident_id")
            return self.path.replace("{id}", incident_id)
        return self.path


IDEMPOTENCY_HEADER = "Idempotency-Key"

API_OPERATIONS: tuple[ApiOperation, ...] = (
    ApiOperation(HttpMethod.GET, "/health", mutating=False, requires_idempotency=False),
    ApiOperation(HttpMethod.GET, "/health/aws", mutating=False, requires_idempotency=False),
    ApiOperation(HttpMethod.GET, "/incidents", mutating=False, requires_idempotency=False),
    ApiOperation(HttpMethod.POST, "/incidents/simulate", mutating=True, requires_idempotency=True),
    ApiOperation(HttpMethod.GET, "/incidents/{id}", mutating=False, requires_idempotency=False),
    ApiOperation(
        HttpMethod.GET, "/incidents/{id}/events", mutating=False, requires_idempotency=False
    ),
    ApiOperation(
        HttpMethod.POST,
        "/incidents/{id}/investigate",
        mutating=True,
        requires_idempotency=True,
    ),
    ApiOperation(
        HttpMethod.POST, "/incidents/{id}/approve", mutating=True, requires_idempotency=True
    ),
    ApiOperation(
        HttpMethod.POST, "/incidents/{id}/reject", mutating=True, requires_idempotency=True
    ),
    ApiOperation(
        HttpMethod.POST, "/incidents/{id}/remediate", mutating=True, requires_idempotency=True
    ),
    ApiOperation(
        HttpMethod.GET, "/incidents/{id}/agent-runs", mutating=False, requires_idempotency=False
    ),
    ApiOperation(HttpMethod.GET, "/metrics/costs", mutating=False, requires_idempotency=False),
    ApiOperation(HttpMethod.GET, "/evaluations", mutating=False, requires_idempotency=False),
)

INCIDENT_RECORD_FIELDS: tuple[str, ...] = (
    "incident_id",
    "service",
    "severity",
    "status",
    "alarm_name",
    "started_at",
    "updated_at",
    "correlation_id",
    "diagnosis",
    "confidence",
    "recommended_action",
    "approval_status",
    "agent_run_id",
    "estimated_ai_cost_usd",
)

DEPLOYMENT_RECORD_FIELDS: tuple[str, ...] = (
    "service",
    "version",
    "commit_sha",
    "deployed_at",
    "change_summary",
)

REQUIRED_AUDIT_EVENT_TYPES: frozenset[EventType] = frozenset(
    {
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
)

LIFECYCLE_STATUSES: tuple[IncidentStatus, ...] = (
    IncidentStatus.DETECTED,
    IncidentStatus.QUEUED,
    IncidentStatus.INVESTIGATING,
    IncidentStatus.DIAGNOSED,
    IncidentStatus.REMEDIATION_PROPOSED,
    IncidentStatus.AWAITING_APPROVAL,
    IncidentStatus.REJECTED,
    IncidentStatus.APPROVED,
    IncidentStatus.REMEDIATING,
    IncidentStatus.FAILED,
    IncidentStatus.RESOLVED,
)

INVESTIGATION_TOOLS: tuple[str, ...] = (
    "query_logs",
    "query_metrics",
    "get_recent_deployments",
    "search_runbooks",
)

DEMO_SERVICES: tuple[str, ...] = (
    "payments-api",
    "orders-api",
    "notifications-worker",
)

PRIMARY_DEMO_SCENARIO = "deployment_regression"

DASHBOARD_ROUTES: tuple[str, ...] = (
    "/incidents",
    "/incidents/[id]",
    "/evaluations",
    "/settings/costs",
)

INCIDENT_LIST_COLUMNS: tuple[str, ...] = (
    "severity",
    "service",
    "status",
    "started_at",
    "probable_cause",
    "confidence",
    "estimated_ai_cost_usd",
)

INCIDENT_DETAIL_SECTIONS: tuple[str, ...] = (
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

EVALUATION_METRICS: tuple[str, ...] = (
    "evaluation_pass_rate",
    "diagnosis_accuracy",
    "groundedness",
    "unsafe_action_count",
    "avg_tool_calls",
    "avg_estimated_cost",
)

COST_SETTINGS_ROUTE = "/settings/costs"
COST_LIMITS_CLIENT_WRITABLE = False

DEMO_SCRIPT_STEPS: tuple[str, ...] = (
    "Open the dashboard with no active incidents.",
    "Run the deployment_regression scenario.",
    "Show the alarm / event.",
    "Show the created incident.",
    "Start the investigation.",
    "Show tool calls and evidence.",
    "Show the retrieved runbook.",
    "Show the diagnosis and confidence.",
    "Show correlation with the recent deployment.",
    "Show the proposed simulated rollback.",
    "Attempt remediation without approval and observe denial.",
    "Approve from the UI.",
    "Execute remediation.",
    "Mark the incident resolved.",
    "Show the trace.",
    "Show tokens, tool calls, and estimated cost.",
    "Show the case evaluation.",
)

REPOSITORY_LAYOUT: tuple[str, ...] = (
    "apps/web",
    "apps/api",
    "services/incident-worker",
    "services/agent",
    "services/tools/cloudwatch",
    "services/tools/deployments",
    "services/tools/knowledge",
    "services/tools/remediation",
    "services/simulator",
    "packages/contracts",
    "packages/observability",
    "packages/cost-guardrails",
    "docs/architecture",
    "docs/runbooks",
    "docs/postmortems",
    "docs/adrs",
    "docs/services",
    "evals",
    "fixtures/incidents",
    "infra/modules",
    "infra/environments/dev",
    "scripts",
    "specs",
    ".github/workflows",
    "Makefile",
    "README.md",
    "AI-Incident-Copilot-Master-Plan.md",
)


def mutating_operations() -> tuple[ApiOperation, ...]:
    return tuple(op for op in API_OPERATIONS if op.mutating)

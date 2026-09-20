"""Pydantic models for incidents, events, evidence, and fixtures."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from incident_contracts.enums import (
    ApprovalStatus,
    EventType,
    EvidenceKind,
    IncidentStatus,
    ScenarioId,
    Severity,
)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    kind: EvidenceKind
    source: str
    summary: str
    observed_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    probable_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)
    retrieved_sources: list[str] = Field(default_factory=list)
    alternative_hypotheses: list[str] = Field(default_factory=list)
    recommended_action: str
    requires_approval: bool = True
    destructive: bool = False


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    incident_id: str
    status: ApprovalStatus
    actor: str
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None = None


class Deployment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    version: str
    commit_sha: str
    deployed_at: datetime
    change_summary: str


class LogSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    service: str
    level: str
    message: str
    fields: dict[str, Any] = Field(default_factory=dict)


class MetricSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    service: str
    name: str
    value: float
    unit: str = "Count"


class TelemetryBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logs: list[LogSample] = Field(default_factory=list)
    metrics: list[MetricSample] = Field(default_factory=list)


class IncidentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    incident_id: str
    event_type: EventType
    timestamp: datetime
    actor: str
    payload: dict[str, Any] = Field(default_factory=dict)
    from_status: IncidentStatus | None = None
    to_status: IncidentStatus | None = None


class Incident(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    service: str
    severity: Severity
    status: IncidentStatus
    alarm_name: str
    started_at: datetime
    updated_at: datetime
    correlation_id: str
    diagnosis: Diagnosis | None = None
    confidence: float | None = None
    recommended_action: str | None = None
    approval_status: ApprovalStatus | None = None
    agent_run_id: str | None = None
    estimated_ai_cost_usd: float = 0.0
    simulation_id: str | None = None
    source_event_id: str | None = None
    active_remediation_id: str | None = None
    approval_id: str | None = None


class IncidentFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: ScenarioId
    seed: str
    incident: Incident
    events: list[IncidentEvent]
    evidence: list[Evidence]
    deployments: list[Deployment]
    expected_diagnosis: Diagnosis
    telemetry: TelemetryBundle
    approval: Approval | None = None

"""Closed enumerations for the incident domain."""

from __future__ import annotations

from enum import StrEnum


class IncidentStatus(StrEnum):
    DETECTED = "DETECTED"
    QUEUED = "QUEUED"
    INVESTIGATING = "INVESTIGATING"
    DIAGNOSED = "DIAGNOSED"
    REMEDIATION_PROPOSED = "REMEDIATION_PROPOSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    REMEDIATING = "REMEDIATING"
    FAILED = "FAILED"
    RESOLVED = "RESOLVED"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventType(StrEnum):
    ALARM_RECEIVED = "ALARM_RECEIVED"
    INVESTIGATION_STARTED = "INVESTIGATION_STARTED"
    TOOL_CALLED = "TOOL_CALLED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    DIAGNOSIS_CREATED = "DIAGNOSIS_CREATED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    REMEDIATION_EXECUTED = "REMEDIATION_EXECUTED"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    STATUS_CHANGED = "STATUS_CHANGED"


class ActorKind(StrEnum):
    SYSTEM = "system"
    AGENT = "agent"
    HUMAN = "human"


class EvidenceKind(StrEnum):
    OBSERVED = "observed_evidence"
    RETRIEVED = "retrieved_guidance"
    INFERENCE = "inference"


class ScenarioId(StrEnum):
    DEPLOYMENT_REGRESSION = "deployment_regression"
    CONNECTION_POOL_EXHAUSTION = "connection_pool_exhaustion"
    QUEUE_BACKLOG = "queue_backlog"
    FALSE_POSITIVE = "false_positive"


class ToolClass(StrEnum):
    READ_ONLY = "READ_ONLY"
    SAFE_WRITE = "SAFE_WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


TERMINAL_STATUSES: frozenset[IncidentStatus] = frozenset(
    {
        IncidentStatus.REJECTED,
        IncidentStatus.FAILED,
        IncidentStatus.RESOLVED,
    }
)

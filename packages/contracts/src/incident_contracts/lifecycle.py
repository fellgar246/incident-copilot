"""Explicit incident lifecycle. Illegal transitions raise, they are never overwritten."""

from __future__ import annotations

from datetime import datetime

from incident_contracts.actors import validate_actor
from incident_contracts.enums import EventType, IncidentStatus
from incident_contracts.errors import IllegalTransitionError
from incident_contracts.models import Incident, IncidentEvent

ALLOWED_TRANSITIONS: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    IncidentStatus.DETECTED: frozenset({IncidentStatus.QUEUED}),
    IncidentStatus.QUEUED: frozenset({IncidentStatus.INVESTIGATING}),
    IncidentStatus.INVESTIGATING: frozenset({IncidentStatus.DIAGNOSED}),
    IncidentStatus.DIAGNOSED: frozenset({IncidentStatus.REMEDIATION_PROPOSED}),
    IncidentStatus.REMEDIATION_PROPOSED: frozenset({IncidentStatus.AWAITING_APPROVAL}),
    IncidentStatus.AWAITING_APPROVAL: frozenset({IncidentStatus.APPROVED, IncidentStatus.REJECTED}),
    IncidentStatus.APPROVED: frozenset({IncidentStatus.REMEDIATING}),
    IncidentStatus.REMEDIATING: frozenset({IncidentStatus.RESOLVED, IncidentStatus.FAILED}),
    IncidentStatus.REJECTED: frozenset(),
    IncidentStatus.FAILED: frozenset(),
    IncidentStatus.RESOLVED: frozenset(),
}

_EVENT_FOR_TARGET: dict[IncidentStatus, EventType] = {
    IncidentStatus.QUEUED: EventType.STATUS_CHANGED,
    IncidentStatus.INVESTIGATING: EventType.INVESTIGATION_STARTED,
    IncidentStatus.DIAGNOSED: EventType.DIAGNOSIS_CREATED,
    IncidentStatus.REMEDIATION_PROPOSED: EventType.STATUS_CHANGED,
    IncidentStatus.AWAITING_APPROVAL: EventType.APPROVAL_REQUESTED,
    IncidentStatus.APPROVED: EventType.APPROVAL_GRANTED,
    IncidentStatus.REJECTED: EventType.APPROVAL_REJECTED,
    IncidentStatus.REMEDIATING: EventType.STATUS_CHANGED,
    IncidentStatus.FAILED: EventType.STATUS_CHANGED,
    IncidentStatus.RESOLVED: EventType.INCIDENT_RESOLVED,
}


def transition(
    incident: Incident,
    target: IncidentStatus,
    *,
    actor: str,
    at: datetime,
    event_id: str,
    payload: dict[str, object] | None = None,
    event_type: EventType | None = None,
) -> tuple[Incident, IncidentEvent]:
    """Apply a legal status change and return the updated incident plus audit event."""
    validate_actor(actor)
    allowed = ALLOWED_TRANSITIONS[incident.status]
    if target not in allowed:
        raise IllegalTransitionError(
            f"Cannot transition {incident.status} -> {target} for {incident.incident_id}"
        )
    event = IncidentEvent(
        event_id=event_id,
        incident_id=incident.incident_id,
        event_type=event_type or _EVENT_FOR_TARGET[target],
        timestamp=at,
        actor=actor,
        payload=payload or {},
        from_status=incident.status,
        to_status=target,
    )
    updated = incident.model_copy(update={"status": target, "updated_at": at})
    return updated, event

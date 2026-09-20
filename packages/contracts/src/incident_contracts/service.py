"""Application service around the lifecycle and an append-only repository."""

from __future__ import annotations

from datetime import datetime

from incident_contracts.enums import ActorKind, ApprovalStatus, EventType, IncidentStatus
from incident_contracts.errors import (
    DuplicateRemediationError,
    IncidentNotFoundError,
    InvalidApprovalError,
)
from incident_contracts.lifecycle import transition
from incident_contracts.models import Approval, Diagnosis, Incident, IncidentEvent
from incident_contracts.repository import IncidentRepository


def format_actor(kind: ActorKind, human_id: str | None = None) -> str:
    if kind is ActorKind.HUMAN:
        if not human_id:
            raise ValueError("human actor requires human_id")
        return f"human:{human_id}"
    return kind.value


class IncidentService:
    def __init__(self, repository: IncidentRepository) -> None:
        self._repo = repository

    def ingest(
        self,
        incident: Incident,
        alarm_event: IncidentEvent,
    ) -> Incident:
        """Create an incident unless the source event_id or simulation_id already exists."""
        existing = None
        if incident.source_event_id:
            existing = self._repo.get_by_source_event_id(incident.source_event_id)
        if existing is None and incident.simulation_id:
            existing = self._repo.get_by_simulation_id(incident.simulation_id)
        if existing is not None:
            return existing
        if self._repo.event_exists(alarm_event.event_id):
            found = self._repo.get_by_source_event_id(alarm_event.event_id)
            if found is not None:
                return found
        self._repo.save(incident)
        self._repo.append_event(alarm_event)
        return incident.model_copy(deep=True)

    def get(self, incident_id: str) -> Incident:
        incident = self._repo.get(incident_id)
        if incident is None:
            raise IncidentNotFoundError(incident_id)
        return incident

    def events(self, incident_id: str) -> list[IncidentEvent]:
        return self._repo.list_events(incident_id)

    def list_incidents(self) -> list[Incident]:
        return self._repo.list_incidents()

    def queue(self, incident_id: str, *, actor: str, at: datetime, event_id: str) -> Incident:
        return self._transition(
            incident_id,
            IncidentStatus.QUEUED,
            actor=actor,
            at=at,
            event_id=event_id,
        )

    def start_investigation(
        self,
        incident_id: str,
        *,
        actor: str,
        at: datetime,
        event_id: str,
        agent_run_id: str,
        correlation_id: str,
    ) -> Incident:
        incident = self._transition(
            incident_id,
            IncidentStatus.INVESTIGATING,
            actor=actor,
            at=at,
            event_id=event_id,
            payload={"agent_run_id": agent_run_id, "correlation_id": correlation_id},
        )
        incident = incident.model_copy(
            update={"agent_run_id": agent_run_id, "correlation_id": correlation_id}
        )
        self._repo.save(incident)
        return incident

    def record_diagnosis(
        self,
        incident_id: str,
        diagnosis: Diagnosis,
        *,
        actor: str,
        at: datetime,
        event_id: str,
    ) -> Incident:
        incident = self._transition(
            incident_id,
            IncidentStatus.DIAGNOSED,
            actor=actor,
            at=at,
            event_id=event_id,
            payload={
                "probable_cause": diagnosis.probable_cause,
                "confidence": diagnosis.confidence,
            },
        )
        incident = incident.model_copy(
            update={
                "diagnosis": diagnosis,
                "confidence": diagnosis.confidence,
                "recommended_action": diagnosis.recommended_action,
            }
        )
        self._repo.save(incident)
        return incident

    def propose_remediation(
        self,
        incident_id: str,
        *,
        actor: str,
        at: datetime,
        event_id: str,
        action: str,
    ) -> Incident:
        return self._transition(
            incident_id,
            IncidentStatus.REMEDIATION_PROPOSED,
            actor=actor,
            at=at,
            event_id=event_id,
            payload={"action": action},
        )

    def request_approval(
        self,
        incident_id: str,
        approval: Approval,
        *,
        actor: str,
        at: datetime,
        event_id: str,
    ) -> Incident:
        incident = self._transition(
            incident_id,
            IncidentStatus.AWAITING_APPROVAL,
            actor=actor,
            at=at,
            event_id=event_id,
            payload={"approval_id": approval.approval_id},
        )
        incident = incident.model_copy(
            update={
                "approval_id": approval.approval_id,
                "approval_status": ApprovalStatus.PENDING,
            }
        )
        self._repo.save(incident)
        return incident

    def approve(
        self,
        incident_id: str,
        *,
        actor: str,
        at: datetime,
        event_id: str,
        approval_id: str,
        expires_at: datetime,
    ) -> Incident:
        incident = self.get(incident_id)
        if incident.approval_id != approval_id:
            raise InvalidApprovalError(f"approval_id mismatch for {incident_id}")
        if at > expires_at:
            raise InvalidApprovalError(f"approval {approval_id} has expired")
        incident = self._transition(
            incident_id,
            IncidentStatus.APPROVED,
            actor=actor,
            at=at,
            event_id=event_id,
            payload={"approval_id": approval_id},
        )
        incident = incident.model_copy(update={"approval_status": ApprovalStatus.GRANTED})
        self._repo.save(incident)
        return incident

    def reject(
        self,
        incident_id: str,
        *,
        actor: str,
        at: datetime,
        event_id: str,
        approval_id: str,
    ) -> Incident:
        incident = self._transition(
            incident_id,
            IncidentStatus.REJECTED,
            actor=actor,
            at=at,
            event_id=event_id,
            payload={"approval_id": approval_id},
        )
        incident = incident.model_copy(update={"approval_status": ApprovalStatus.REJECTED})
        self._repo.save(incident)
        return incident

    def start_remediation(
        self,
        incident_id: str,
        *,
        actor: str,
        at: datetime,
        event_id: str,
        remediation_id: str,
        approval_id: str,
    ) -> Incident:
        incident = self.get(incident_id)
        if incident.active_remediation_id is not None:
            raise DuplicateRemediationError(
                f"incident {incident_id} already has remediation {incident.active_remediation_id}"
            )
        if incident.approval_id != approval_id:
            raise InvalidApprovalError("valid approval_id is required to remediate")
        incident = self._transition(
            incident_id,
            IncidentStatus.REMEDIATING,
            actor=actor,
            at=at,
            event_id=event_id,
            payload={"remediation_id": remediation_id, "approval_id": approval_id},
        )
        incident = incident.model_copy(update={"active_remediation_id": remediation_id})
        self._repo.save(incident)
        return incident

    def complete_remediation(
        self,
        incident_id: str,
        *,
        actor: str,
        at: datetime,
        event_id: str,
        success: bool,
    ) -> Incident:
        if success:
            self._repo.append_event(
                IncidentEvent(
                    event_id=f"{event_id}-exec",
                    incident_id=incident_id,
                    event_type=EventType.REMEDIATION_EXECUTED,
                    timestamp=at,
                    actor=actor,
                    payload={"success": True},
                    from_status=IncidentStatus.REMEDIATING,
                    to_status=IncidentStatus.REMEDIATING,
                )
            )
        target = IncidentStatus.RESOLVED if success else IncidentStatus.FAILED
        incident = self._transition(
            incident_id,
            target,
            actor=actor,
            at=at,
            event_id=event_id,
            payload={"success": success},
        )
        incident = incident.model_copy(update={"active_remediation_id": None})
        self._repo.save(incident)
        return incident

    def _transition(
        self,
        incident_id: str,
        target: IncidentStatus,
        *,
        actor: str,
        at: datetime,
        event_id: str,
        payload: dict[str, object] | None = None,
        event_type: EventType | None = None,
    ) -> Incident:
        if self._repo.event_exists(event_id):
            return self.get(incident_id)
        incident = self.get(incident_id)
        updated, event = transition(
            incident,
            target,
            actor=actor,
            at=at,
            event_id=event_id,
            payload=payload,
            event_type=event_type,
        )
        self._repo.save(updated)
        self._repo.append_event(event)
        return updated

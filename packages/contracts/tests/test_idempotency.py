from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from incident_contracts.enums import ActorKind, EventType, IncidentStatus
from incident_contracts.errors import DuplicateRemediationError, IllegalTransitionError
from incident_contracts.models import Approval, Diagnosis, Incident, IncidentEvent, Severity
from incident_contracts.repository import InMemoryIncidentRepository
from incident_contracts.service import IncidentService

NOW = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)


def _service() -> IncidentService:
    return IncidentService(InMemoryIncidentRepository())


def _new_incident(event_id: str = "evt_alarm") -> tuple[Incident, IncidentEvent]:
    incident = Incident(
        incident_id="inc_1",
        service="payments-api",
        severity=Severity.HIGH,
        status=IncidentStatus.DETECTED,
        alarm_name="payments-5xx-rate",
        started_at=NOW,
        updated_at=NOW,
        correlation_id="cor_1",
        simulation_id="sim_1",
        source_event_id=event_id,
    )
    event = IncidentEvent(
        event_id=event_id,
        incident_id="inc_1",
        event_type=EventType.ALARM_RECEIVED,
        timestamp=NOW,
        actor=ActorKind.SYSTEM.value,
        to_status=IncidentStatus.DETECTED,
    )
    return incident, event


def test_duplicate_event_id_does_not_create_second_incident() -> None:
    service = _service()
    incident, event = _new_incident()
    first = service.ingest(incident, event)
    clone = incident.model_copy(update={"incident_id": "inc_other"})
    second = service.ingest(clone, event)
    assert first.incident_id == second.incident_id == "inc_1"
    assert len(service.list_incidents()) == 1


def test_duplicate_simulation_id_is_idempotent() -> None:
    service = _service()
    incident, event = _new_incident()
    service.ingest(incident, event)
    other_event = event.model_copy(update={"event_id": "evt_other"})
    other = incident.model_copy(update={"incident_id": "inc_2", "source_event_id": "evt_other"})
    reused = service.ingest(other, other_event)
    assert reused.incident_id == "inc_1"


def test_full_happy_path_and_single_active_remediation() -> None:
    service = _service()
    incident, event = _new_incident()
    service.ingest(incident, event)
    service.queue("inc_1", actor="system", at=NOW, event_id="evt_q")
    service.start_investigation(
        "inc_1",
        actor="agent",
        at=NOW,
        event_id="evt_inv",
        agent_run_id="run_1",
        correlation_id="cor_1",
    )
    diagnosis = Diagnosis(
        summary="regression",
        probable_cause="deploy",
        confidence=0.9,
        recommended_action="rollback",
        requires_approval=True,
    )
    service.record_diagnosis("inc_1", diagnosis, actor="agent", at=NOW, event_id="evt_dx")
    service.propose_remediation(
        "inc_1", actor="agent", at=NOW, event_id="evt_pr", action="rollback"
    )
    approval = Approval(
        approval_id="appr_1",
        incident_id="inc_1",
        status="PENDING",
        actor="human:ada",
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    service.request_approval("inc_1", approval, actor="agent", at=NOW, event_id="evt_appr")
    service.approve(
        "inc_1",
        actor="human:ada",
        at=NOW,
        event_id="evt_ok",
        approval_id="appr_1",
        expires_at=approval.expires_at,
    )
    service.start_remediation(
        "inc_1",
        actor="system",
        at=NOW,
        event_id="evt_rem",
        remediation_id="rem_1",
        approval_id="appr_1",
    )
    with pytest.raises(DuplicateRemediationError):
        service.start_remediation(
            "inc_1",
            actor="system",
            at=NOW,
            event_id="evt_rem2",
            remediation_id="rem_2",
            approval_id="appr_1",
        )
    resolved = service.complete_remediation(
        "inc_1", actor="system", at=NOW, event_id="evt_done", success=True
    )
    assert resolved.status is IncidentStatus.RESOLVED
    events = service.events("inc_1")
    assert events[0].event_type is EventType.ALARM_RECEIVED
    types = [item.event_type for item in events]
    assert EventType.REMEDIATION_EXECUTED in types
    assert EventType.INCIDENT_RESOLVED in types


def test_cannot_skip_states() -> None:
    service = _service()
    incident, event = _new_incident()
    service.ingest(incident, event)
    with pytest.raises(IllegalTransitionError):
        service.start_investigation(
            "inc_1",
            actor="agent",
            at=NOW,
            event_id="evt_skip",
            agent_run_id="run_1",
            correlation_id="cor_1",
        )


def test_replay_event_id_does_not_append_second_event() -> None:
    service = _service()
    incident, event = _new_incident()
    service.ingest(incident, event)
    first = service.queue("inc_1", actor="system", at=NOW, event_id="evt_q")
    second = service.queue("inc_1", actor="system", at=NOW, event_id="evt_q")
    assert first.status is second.status is IncidentStatus.QUEUED
    matching = [item for item in service.events("inc_1") if item.event_id == "evt_q"]
    assert len(matching) == 1


def test_list_incidents_filters_by_service_and_status() -> None:
    service = _service()
    incident, event = _new_incident()
    service.ingest(incident, event)
    other_event = event.model_copy(update={"event_id": "evt_other"})
    other = incident.model_copy(
        update={
            "incident_id": "inc_2",
            "service": "orders-api",
            "source_event_id": "evt_other",
            "simulation_id": "sim_2",
        }
    )
    service.ingest(other, other_event)
    only_orders = service.list_incidents(service="orders-api")
    assert [item.incident_id for item in only_orders] == ["inc_2"]
    detected = service.list_incidents(status=IncidentStatus.DETECTED)
    assert {item.incident_id for item in detected} == {"inc_1", "inc_2"}


def _approve(service: IncidentService) -> None:
    incident, event = _new_incident()
    service.ingest(incident, event)
    service.queue("inc_1", actor="system", at=NOW, event_id="evt_q")
    service.start_investigation(
        "inc_1",
        actor="agent",
        at=NOW,
        event_id="evt_inv",
        agent_run_id="run_1",
        correlation_id="cor_1",
    )
    diagnosis = Diagnosis(
        summary="regression",
        probable_cause="deploy",
        confidence=0.9,
        recommended_action="rollback",
        requires_approval=True,
    )
    service.record_diagnosis("inc_1", diagnosis, actor="agent", at=NOW, event_id="evt_dx")
    service.propose_remediation(
        "inc_1", actor="agent", at=NOW, event_id="evt_pr", action="rollback"
    )
    approval = Approval(
        approval_id="appr_1",
        incident_id="inc_1",
        status="PENDING",
        actor="human:ada",
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    service.request_approval("inc_1", approval, actor="agent", at=NOW, event_id="evt_appr")
    service.approve(
        "inc_1",
        actor="human:ada",
        at=NOW,
        event_id="evt_ok",
        approval_id="appr_1",
        expires_at=approval.expires_at,
    )


def test_replay_start_remediation_same_event_id_is_idempotent() -> None:
    service = _service()
    _approve(service)
    first = service.start_remediation(
        "inc_1",
        actor="system",
        at=NOW,
        event_id="evt_rem",
        remediation_id="rem_1",
        approval_id="appr_1",
    )
    second = service.start_remediation(
        "inc_1",
        actor="system",
        at=NOW,
        event_id="evt_rem",
        remediation_id="rem_1",
        approval_id="appr_1",
    )
    assert first.active_remediation_id == second.active_remediation_id == "rem_1"
    remediations = [item for item in service.events("inc_1") if item.event_id == "evt_rem"]
    assert len(remediations) == 1

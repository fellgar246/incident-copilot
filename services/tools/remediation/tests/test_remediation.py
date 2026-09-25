from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from incident_contracts.enums import ApprovalStatus, EventType, IncidentStatus
from incident_contracts.errors import DuplicateRemediationError, RemediationDeniedError
from incident_contracts.models import Diagnosis
from incident_contracts.repository import InMemoryIncidentRepository
from incident_contracts.service import IncidentService
from remediation_tool.actions import classify_action
from remediation_tool.tools import RemediationTools, attempt_remediation

from simulator import simulate

NOW = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)


def _diagnosed() -> tuple[IncidentService, str]:
    fixture = simulate("deployment_regression", seed="remediation")
    service = IncidentService(InMemoryIncidentRepository())
    service.ingest_fixture(fixture)
    incident_id = fixture.incident.incident_id
    service.queue(incident_id, actor="system", at=NOW, event_id="evt_q")
    service.start_investigation(
        incident_id,
        actor="agent",
        at=NOW,
        event_id="evt_inv",
        agent_run_id="run_1",
        correlation_id=fixture.incident.correlation_id,
    )
    service.record_diagnosis(
        incident_id,
        Diagnosis(
            summary="regression",
            probable_cause="deploy",
            confidence=0.9,
            recommended_action="rollback_simulated",
            requires_approval=True,
        ),
        actor="agent",
        at=NOW,
        event_id="evt_dx",
    )
    return service, incident_id


def _tools(service: IncidentService, **env: str) -> RemediationTools:
    base = {"REMEDIATION_ENABLED": "true", "APPROVAL_TTL_SECONDS": "60"}
    base.update(env)
    return RemediationTools(service, environ=base, clock=lambda: NOW)


def _propose(tools: RemediationTools, incident_id: str) -> dict[str, object]:
    return tools.request_remediation(
        {
            "incident_id": incident_id,
            "action": "rollback_simulated",
            "rationale": "5xx rose after the latest deploy",
        },
        at=NOW,
    )


def test_request_does_not_execute_and_waits_for_approval() -> None:
    service, incident_id = _diagnosed()
    tools = _tools(service)
    body = _propose(tools, incident_id)
    incident = service.get(incident_id)
    assert body["executed"] is False
    assert body["status"] == "AWAITING_APPROVAL"
    assert incident.status is IncidentStatus.AWAITING_APPROVAL
    assert incident.proposal is not None
    assert incident.proposal.action == "rollback_simulated"
    assert incident.proposal.requires_approval is True
    assert tools.simulator.logical_version == {}
    types = [event.event_type for event in service.events(incident_id)]
    assert EventType.APPROVAL_REQUESTED in types
    assert EventType.REMEDIATION_EXECUTED not in types


def test_attempt_without_approval_is_denied() -> None:
    service, incident_id = _diagnosed()
    tools = _tools(service)
    _propose(tools, incident_id)
    assert attempt_remediation(tools, incident_id, approval_id="appr_missing", at=NOW) == "DENIED"
    assert service.get(incident_id).status is IncidentStatus.AWAITING_APPROVAL
    assert tools.simulator.logical_version == {}


def test_expired_approval_is_denied() -> None:
    service, incident_id = _diagnosed()
    tools = _tools(service, APPROVAL_TTL_SECONDS="30")
    body = _propose(tools, incident_id)
    approval_id = str(body["approval_id"])
    service.approve(
        incident_id,
        actor="human:demo",
        at=NOW,
        event_id="evt_ok",
        approval_id=approval_id,
        expires_at=NOW + timedelta(seconds=30),
    )
    with pytest.raises(RemediationDeniedError, match="expired"):
        tools.execute_remediation(
            incident_id,
            approval_id=approval_id,
            idempotency_key="exec-late",
            actor="human:demo",
            at=NOW + timedelta(seconds=31),
        )
    assert service.get(incident_id).status is IncidentStatus.APPROVED
    assert tools.simulator.logical_version == {}


def test_execute_is_idempotent_and_resolves() -> None:
    service, incident_id = _diagnosed()
    tools = _tools(service)
    body = _propose(tools, incident_id)
    approval_id = str(body["approval_id"])
    service.approve(
        incident_id,
        actor="human:demo",
        at=NOW,
        event_id="evt_ok",
        approval_id=approval_id,
        expires_at=NOW + timedelta(seconds=60),
    )
    first = tools.execute_remediation(
        incident_id,
        approval_id=approval_id,
        idempotency_key="exec-1",
        actor="human:demo",
        at=NOW,
    )
    second = tools.execute_remediation(
        incident_id,
        approval_id=approval_id,
        idempotency_key="exec-1",
        actor="human:demo",
        at=NOW,
    )
    assert first.status is second.status is IncidentStatus.RESOLVED
    assert first.incident_id == second.incident_id
    executed = [
        event
        for event in service.events(incident_id)
        if event.event_type is EventType.REMEDIATION_EXECUTED
    ]
    assert len(executed) == 1
    assert executed[0].actor == "human:demo"
    assert tools.simulator.logical_version[first.service] == "previous"
    stored = service.get(incident_id)
    assert stored.approval is not None
    assert stored.approval.status is ApprovalStatus.GRANTED


def test_repeated_request_is_rejected() -> None:
    service, incident_id = _diagnosed()
    tools = _tools(service)
    _propose(tools, incident_id)
    with pytest.raises(DuplicateRemediationError):
        _propose(tools, incident_id)
    assert service.get(incident_id).status is IncidentStatus.AWAITING_APPROVAL


def test_destructive_and_unknown_actions_are_impossible() -> None:
    service, incident_id = _diagnosed()
    tools = _tools(service)
    for action in ("restart_service", "run_shell", "bash -c reboot", "scale_out"):
        with pytest.raises(RemediationDeniedError):
            tools.request_remediation(
                {"incident_id": incident_id, "action": action, "rationale": "no"},
                at=NOW,
            )
    assert service.get(incident_id).status is IncidentStatus.DIAGNOSED
    with pytest.raises(RemediationDeniedError, match="DESTRUCTIVE"):
        classify_action("terminate_instance")


def test_disabled_flag_denies_execution() -> None:
    service, incident_id = _diagnosed()
    tools = _tools(service, REMEDIATION_ENABLED="false")
    body = _propose(tools, incident_id)
    approval_id = str(body["approval_id"])
    service.approve(
        incident_id,
        actor="human:demo",
        at=NOW,
        event_id="evt_ok",
        approval_id=approval_id,
        expires_at=NOW + timedelta(seconds=60),
    )
    assert (
        attempt_remediation(
            tools,
            incident_id,
            approval_id=approval_id,
            idempotency_key="exec-off",
            at=NOW,
        )
        == "DENIED"
    )
    assert tools.simulator.logical_version == {}


def test_reject_stops_the_incident() -> None:
    service, incident_id = _diagnosed()
    tools = _tools(service)
    body = _propose(tools, incident_id)
    rejected = service.reject(
        incident_id,
        actor="human:demo",
        at=NOW,
        event_id="evt_no",
        approval_id=str(body["approval_id"]),
    )
    assert rejected.status is IncidentStatus.REJECTED
    assert rejected.approval is not None
    assert rejected.approval.status is ApprovalStatus.REJECTED
    assert attempt_remediation(tools, incident_id, at=NOW) == "DENIED"

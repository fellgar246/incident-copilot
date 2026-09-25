from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from incident_contracts.enums import IncidentStatus, ScenarioId
from incident_contracts.models import Diagnosis
from incident_contracts.repository import InMemoryIncidentRepository
from incident_contracts.service import IncidentService
from remediation_tool.tools import RemediationTools

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def _diagnosed(repository: InMemoryIncidentRepository, client: TestClient) -> str:
    created = client.post(
        "/incidents/simulate",
        json={"scenario": ScenarioId.DEPLOYMENT_REGRESSION.value, "seed": "api-rem"},
    )
    assert created.status_code == 201
    incident_id = created.json()["incident_id"]
    service = IncidentService(repository)
    service.queue(incident_id, actor="system", at=NOW, event_id="evt_q")
    service.start_investigation(
        incident_id,
        actor="agent",
        at=NOW,
        event_id="evt_inv",
        agent_run_id="run_1",
        correlation_id="cor_api",
    )
    service.record_diagnosis(
        incident_id,
        Diagnosis(
            summary="regression",
            probable_cause="deploy",
            confidence=0.91,
            recommended_action="rollback_simulated",
            requires_approval=True,
        ),
        actor="agent",
        at=NOW,
        event_id="evt_dx",
    )
    proposal = RemediationTools(service).request_remediation(
        {
            "incident_id": incident_id,
            "action": "rollback_simulated",
            "rationale": "errors started after the deploy",
        }
    )
    assert proposal["executed"] is False
    return f"{incident_id}|{proposal['approval_id']}"


def test_remediate_without_approval_is_denied(
    client: TestClient, repository: InMemoryIncidentRepository
) -> None:
    token = _diagnosed(repository, client)
    incident_id, approval_id = token.split("|", 1)
    denied = client.post(
        f"/incidents/{incident_id}/remediate",
        headers={"Idempotency-Key": "no-grant", "X-Actor": "human:demo"},
        json={"approval_id": approval_id},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["decision"] == "DENIED"
    assert repository.get(incident_id) is not None
    assert repository.get(incident_id).status is IncidentStatus.AWAITING_APPROVAL  # type: ignore[union-attr]


def test_approve_then_execute_resolves_once(
    client: TestClient, repository: InMemoryIncidentRepository
) -> None:
    token = _diagnosed(repository, client)
    incident_id, approval_id = token.split("|", 1)
    headers = {"X-Actor": "human:demo"}
    approved = client.post(
        f"/incidents/{incident_id}/approve",
        headers={**headers, "Idempotency-Key": "grant-1"},
        json={"approval_id": approval_id},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    replay = client.post(
        f"/incidents/{incident_id}/approve",
        headers={**headers, "Idempotency-Key": "grant-1"},
        json={"approval_id": approval_id},
    )
    assert replay.status_code == 200
    executed = client.post(
        f"/incidents/{incident_id}/remediate",
        headers={**headers, "Idempotency-Key": "exec-1"},
        json={"approval_id": approval_id},
    )
    assert executed.status_code == 200
    assert executed.json()["status"] == "RESOLVED"
    again = client.post(
        f"/incidents/{incident_id}/remediate",
        headers={**headers, "Idempotency-Key": "exec-1"},
        json={"approval_id": approval_id},
    )
    assert again.status_code == 200
    assert again.json()["incident_id"] == incident_id
    executed_events = [
        event
        for event in client.get(f"/incidents/{incident_id}/events").json()
        if event["event_type"] == "REMEDIATION_EXECUTED"
    ]
    assert len(executed_events) == 1
    assert executed_events[0]["actor"] == "human:demo"


def test_reject_blocks_execution(
    client: TestClient, repository: InMemoryIncidentRepository
) -> None:
    token = _diagnosed(repository, client)
    incident_id, approval_id = token.split("|", 1)
    rejected = client.post(
        f"/incidents/{incident_id}/reject",
        headers={"Idempotency-Key": "no-1", "X-Actor": "human:demo"},
        json={"approval_id": approval_id, "reason": "not now"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    denied = client.post(
        f"/incidents/{incident_id}/remediate",
        headers={"Idempotency-Key": "exec-no", "X-Actor": "human:demo"},
        json={"approval_id": approval_id},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["decision"] == "DENIED"

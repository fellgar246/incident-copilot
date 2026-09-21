from __future__ import annotations

from datetime import UTC, datetime, timedelta

import boto3
from api.persistence.dynamodb import DynamoIncidentRepository
from incident_contracts.enums import ActorKind, EventType, IncidentStatus, Severity
from incident_contracts.models import Deployment, Incident, IncidentEvent
from incident_contracts.service import IncidentService
from moto import mock_aws

from simulator import simulate

NOW = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
REGION = "us-east-1"
INCIDENTS = "test-incidents"
DEPLOYMENTS = "test-deployments"


def _create_tables(client: object) -> None:
    for name in (INCIDENTS, DEPLOYMENTS):
        client.create_table(
            TableName=name,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )


def _repo() -> DynamoIncidentRepository:
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    return DynamoIncidentRepository(
        dynamodb.Table(INCIDENTS),
        dynamodb.Table(DEPLOYMENTS),
        retention_days=7,
    )


def _incident(incident_id: str = "inc_ddb") -> Incident:
    return Incident(
        incident_id=incident_id,
        service="payments-api",
        severity=Severity.HIGH,
        status=IncidentStatus.DETECTED,
        alarm_name="payments-5xx-rate",
        started_at=NOW,
        updated_at=NOW,
        correlation_id="cor_ddb",
        simulation_id="sim_ddb",
        source_event_id="evt_alarm",
    )


def _event(event_id: str, timestamp: datetime | None = None) -> IncidentEvent:
    return IncidentEvent(
        event_id=event_id,
        incident_id="inc_ddb",
        event_type=EventType.ALARM_RECEIVED
        if event_id == "evt_alarm"
        else EventType.EVIDENCE_ADDED,
        timestamp=timestamp or NOW,
        actor=ActorKind.SYSTEM.value,
        to_status=IncidentStatus.DETECTED,
    )


@mock_aws
def test_put_get_query_and_duplicate_event() -> None:
    client = boto3.client("dynamodb", region_name=REGION)
    _create_tables(client)
    repo = _repo()
    service = IncidentService(repo)
    incident = _incident()
    first_event = _event("evt_alarm")
    later = _event("evt_evidence", NOW + timedelta(seconds=2))

    service.ingest(incident, first_event)
    repo.append_event(later)
    repo.append_event(later)

    loaded = repo.get("inc_ddb")
    assert loaded is not None
    assert loaded.incident_id == "inc_ddb"
    assert repo.get_by_simulation_id("sim_ddb") is not None
    assert repo.get_by_source_event_id("evt_alarm") is not None

    events = repo.list_events("inc_ddb")
    assert [item.event_id for item in events] == ["evt_alarm", "evt_evidence"]
    assert events[0].timestamp <= events[1].timestamp
    assert repo.event_exists("evt_evidence") is True

    listed = repo.list_incidents(status=IncidentStatus.DETECTED, service="payments-api")
    assert len(listed) == 1


@mock_aws
def test_duplicate_ingest_does_not_create_second_incident() -> None:
    client = boto3.client("dynamodb", region_name=REGION)
    _create_tables(client)
    repo = _repo()
    service = IncidentService(repo)
    fixture = simulate("deployment_regression", seed="ddb-dup")
    first = service.ingest_fixture(fixture)
    second = service.ingest_fixture(fixture)
    assert first.incident_id == second.incident_id
    assert len(service.list_incidents()) == 1
    event_ids = [item.event_id for item in service.events(first.incident_id)]
    assert event_ids
    assert len(event_ids) == len(set(event_ids))


@mock_aws
def test_deployments_and_idempotency_index() -> None:
    client = boto3.client("dynamodb", region_name=REGION)
    _create_tables(client)
    repo = _repo()
    deployment = Deployment(
        service="payments-api",
        version="2026.09.20.3",
        commit_sha="abc123def456",
        deployed_at=NOW,
        change_summary="timeout change",
    )
    repo.save_many([deployment])
    found = repo.list_deployments("payments-api")
    assert len(found) == 1
    assert found[0].version == "2026.09.20.3"

    incident = _incident()
    repo.save(incident)
    repo.remember_idempotency("key-1", incident.incident_id)
    repo.remember_idempotency("key-1", "inc_other")
    loaded = repo.get_by_idempotency_key("key-1")
    assert loaded is not None
    assert loaded.incident_id == "inc_ddb"

    ping = repo.ping()
    assert ping["repository"] == "dynamodb"
    assert ping["status"] == "ok"

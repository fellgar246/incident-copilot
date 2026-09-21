from __future__ import annotations

from datetime import UTC, datetime, timedelta

from api.persistence.mapping import (
    ENTITY_EVENT,
    ENTITY_INCIDENT,
    event_from_item,
    event_item,
    incident_from_item,
    incident_item,
    ttl_epoch,
)
from incident_contracts.enums import ActorKind, EventType, IncidentStatus, Severity
from incident_contracts.keys import (
    INDEX_SK,
    METADATA_SK,
    deployment_pk,
    deployment_sk,
    event_id_pk,
    event_sk,
    idempotency_pk,
    incident_pk,
    simulation_pk,
    source_event_pk,
)
from incident_contracts.models import Incident, IncidentEvent

NOW = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)


def _incident() -> Incident:
    return Incident(
        incident_id="inc_map",
        service="payments-api",
        severity=Severity.HIGH,
        status=IncidentStatus.DETECTED,
        alarm_name="payments-5xx-rate",
        started_at=NOW,
        updated_at=NOW,
        correlation_id="cor_map",
        simulation_id="sim_map",
        source_event_id="evt_map",
    )


def test_incident_item_uses_contract_keys_and_round_trips() -> None:
    incident = _incident()
    item = incident_item(incident, expires_at=ttl_epoch(NOW, 7))
    assert item["pk"] == incident_pk("inc_map") == "INCIDENT#inc_map"
    assert item["sk"] == METADATA_SK
    assert item["entity_type"] == ENTITY_INCIDENT
    assert item["status"] == "DETECTED"
    assert item["service"] == "payments-api"
    restored = incident_from_item(item)
    assert restored.incident_id == incident.incident_id
    assert restored.correlation_id == incident.correlation_id


def test_event_item_is_append_only_sort_key() -> None:
    event = IncidentEvent(
        event_id="evt_map",
        incident_id="inc_map",
        event_type=EventType.ALARM_RECEIVED,
        timestamp=NOW,
        actor=ActorKind.SYSTEM.value,
        to_status=IncidentStatus.DETECTED,
    )
    later = IncidentEvent(
        event_id="evt_later",
        incident_id="inc_map",
        event_type=EventType.EVIDENCE_ADDED,
        timestamp=NOW + timedelta(seconds=5),
        actor=ActorKind.SYSTEM.value,
    )
    first = event_item(event, expires_at=1)
    second = event_item(later, expires_at=1)
    assert first["pk"] == "INCIDENT#inc_map"
    assert first["sk"] == event_sk(NOW, "evt_map")
    assert first["sk"].startswith("EVENT#")
    assert first["sk"] < second["sk"]
    assert first["entity_type"] == ENTITY_EVENT
    assert event_from_item(first).event_id == "evt_map"


def test_uniqueness_and_deployment_keys() -> None:
    assert source_event_pk("evt_1") == "SOURCE#evt_1"
    assert simulation_pk("sim_1") == "SIMULATION#sim_1"
    assert event_id_pk("evt_1") == "EVENTID#evt_1"
    assert idempotency_pk("demo-key") == "IDEM#demo-key"
    assert INDEX_SK == "INDEX"
    assert deployment_pk("payments-api") == "SERVICE#payments-api"
    assert deployment_sk(NOW, "2026.09.20.3") == "DEPLOY#2026-09-20T14:00:00.000Z#2026.09.20.3"


def test_ttl_is_unix_epoch_seconds() -> None:
    expires = ttl_epoch(NOW, 7)
    assert expires == int((NOW + timedelta(days=7)).timestamp())

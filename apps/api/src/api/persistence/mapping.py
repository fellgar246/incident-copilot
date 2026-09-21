"""Serialize domain objects to DynamoDB items and back."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from incident_contracts.enums import IncidentStatus
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
from incident_contracts.models import Deployment, Incident, IncidentEvent

ENTITY_INCIDENT = "INCIDENT"
ENTITY_EVENT = "EVENT"
ENTITY_INDEX = "INDEX"
ENTITY_DEPLOYMENT = "DEPLOYMENT"

ATTR_PK = "pk"
ATTR_SK = "sk"
ATTR_ENTITY_TYPE = "entity_type"
ATTR_DOCUMENT = "document"
ATTR_INCIDENT_ID = "incident_id"
ATTR_STATUS = "status"
ATTR_SERVICE = "service"
ATTR_STARTED_AT = "started_at"
ATTR_EXPIRES_AT = "expires_at"


def ttl_epoch(now: datetime, retention_days: int) -> int:
    if now.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    expires = now.astimezone(UTC) + timedelta(days=retention_days)
    return int(expires.timestamp())


def incident_item(incident: Incident, *, expires_at: int) -> dict[str, Any]:
    return {
        ATTR_PK: incident_pk(incident.incident_id),
        ATTR_SK: METADATA_SK,
        ATTR_ENTITY_TYPE: ENTITY_INCIDENT,
        ATTR_INCIDENT_ID: incident.incident_id,
        ATTR_STATUS: incident.status.value,
        ATTR_SERVICE: incident.service,
        ATTR_STARTED_AT: incident.started_at.astimezone(UTC).isoformat(),
        ATTR_DOCUMENT: incident.model_dump_json(),
        ATTR_EXPIRES_AT: expires_at,
    }


def event_item(event: IncidentEvent, *, expires_at: int) -> dict[str, Any]:
    return {
        ATTR_PK: incident_pk(event.incident_id),
        ATTR_SK: event_sk(event.timestamp, event.event_id),
        ATTR_ENTITY_TYPE: ENTITY_EVENT,
        ATTR_INCIDENT_ID: event.incident_id,
        ATTR_DOCUMENT: event.model_dump_json(),
        ATTR_EXPIRES_AT: expires_at,
    }


def index_item(pk: str, incident_id: str, *, expires_at: int) -> dict[str, Any]:
    return {
        ATTR_PK: pk,
        ATTR_SK: INDEX_SK,
        ATTR_ENTITY_TYPE: ENTITY_INDEX,
        ATTR_INCIDENT_ID: incident_id,
        ATTR_EXPIRES_AT: expires_at,
    }


def source_index_item(event_id: str, incident_id: str, *, expires_at: int) -> dict[str, Any]:
    return index_item(source_event_pk(event_id), incident_id, expires_at=expires_at)


def simulation_index_item(
    simulation_id: str, incident_id: str, *, expires_at: int
) -> dict[str, Any]:
    return index_item(simulation_pk(simulation_id), incident_id, expires_at=expires_at)


def event_id_index_item(event_id: str, incident_id: str, *, expires_at: int) -> dict[str, Any]:
    return index_item(event_id_pk(event_id), incident_id, expires_at=expires_at)


def idempotency_index_item(key: str, incident_id: str, *, expires_at: int) -> dict[str, Any]:
    return index_item(idempotency_pk(key), incident_id, expires_at=expires_at)


def deployment_item(deployment: Deployment, *, expires_at: int) -> dict[str, Any]:
    return {
        ATTR_PK: deployment_pk(deployment.service),
        ATTR_SK: deployment_sk(deployment.deployed_at, deployment.version),
        ATTR_ENTITY_TYPE: ENTITY_DEPLOYMENT,
        ATTR_SERVICE: deployment.service,
        ATTR_DOCUMENT: deployment.model_dump_json(),
        ATTR_EXPIRES_AT: expires_at,
    }


def incident_from_item(item: dict[str, Any]) -> Incident:
    return Incident.model_validate_json(str(item[ATTR_DOCUMENT]))


def event_from_item(item: dict[str, Any]) -> IncidentEvent:
    return IncidentEvent.model_validate_json(str(item[ATTR_DOCUMENT]))


def deployment_from_item(item: dict[str, Any]) -> Deployment:
    return Deployment.model_validate_json(str(item[ATTR_DOCUMENT]))


def matches_filters(
    item: dict[str, Any],
    *,
    status: IncidentStatus | None,
    service: str | None,
) -> bool:
    if item.get(ATTR_ENTITY_TYPE) != ENTITY_INCIDENT:
        return False
    if status is not None and item.get(ATTR_STATUS) != status.value:
        return False
    if service is not None and item.get(ATTR_SERVICE) != service:
        return False
    return True

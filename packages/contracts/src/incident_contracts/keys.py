"""Persistence key helpers. Formats are part of the product contract."""

from __future__ import annotations

from datetime import UTC, datetime

INCIDENT_PK_PREFIX = "INCIDENT#"
EVENT_SK_PREFIX = "EVENT#"
METADATA_SK = "METADATA"
INDEX_SK = "INDEX"
SOURCE_PK_PREFIX = "SOURCE#"
SIMULATION_PK_PREFIX = "SIMULATION#"
EVENT_ID_PK_PREFIX = "EVENTID#"
IDEMPOTENCY_PK_PREFIX = "IDEM#"
SERVICE_PK_PREFIX = "SERVICE#"
DEPLOY_SK_PREFIX = "DEPLOY#"


def incident_pk(incident_id: str) -> str:
    """Return PK = INCIDENT#{incident_id}."""
    if not incident_id:
        raise ValueError("incident_id is required")
    if incident_id.startswith(INCIDENT_PK_PREFIX):
        raise ValueError("incident_id must not include the partition-key prefix")
    return f"{INCIDENT_PK_PREFIX}{incident_id}"


def parse_incident_pk(pk: str) -> str:
    if not pk.startswith(INCIDENT_PK_PREFIX) or pk == INCIDENT_PK_PREFIX:
        raise ValueError(f"invalid incident partition key: {pk}")
    return pk.removeprefix(INCIDENT_PK_PREFIX)


def utc_sort_timestamp(moment: datetime) -> str:
    """UTC millisecond timestamp that sorts lexicographically."""
    if moment.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    iso = moment.astimezone(UTC).isoformat(timespec="milliseconds")
    return iso.replace("+00:00", "Z")


def event_sk(timestamp: datetime, event_id: str) -> str:
    """Return SK = EVENT#{timestamp}#{event_id}."""
    if not event_id:
        raise ValueError("event_id is required")
    if "#" in event_id:
        raise ValueError("event_id must not contain '#'")
    return f"{EVENT_SK_PREFIX}{utc_sort_timestamp(timestamp)}#{event_id}"


def parse_event_sk(sk: str) -> tuple[str, str]:
    if not sk.startswith(EVENT_SK_PREFIX) or sk == EVENT_SK_PREFIX:
        raise ValueError(f"invalid event sort key: {sk}")
    rest = sk.removeprefix(EVENT_SK_PREFIX)
    timestamp, separator, event_id = rest.partition("#")
    if not separator or not timestamp or not event_id:
        raise ValueError(f"invalid event sort key: {sk}")
    return timestamp, event_id


def _require_token(value: str, name: str) -> str:
    if not value:
        raise ValueError(f"{name} is required")
    if "#" in value:
        raise ValueError(f"{name} must not contain '#'")
    return value


def source_event_pk(event_id: str) -> str:
    """Return PK = SOURCE#{source_event_id} for idempotent alarm ingestion."""
    return f"{SOURCE_PK_PREFIX}{_require_token(event_id, 'event_id')}"


def simulation_pk(simulation_id: str) -> str:
    """Return PK = SIMULATION#{simulation_id}."""
    return f"{SIMULATION_PK_PREFIX}{_require_token(simulation_id, 'simulation_id')}"


def event_id_pk(event_id: str) -> str:
    """Return PK = EVENTID#{event_id} so event rows stay unique."""
    return f"{EVENT_ID_PK_PREFIX}{_require_token(event_id, 'event_id')}"


def idempotency_pk(key: str) -> str:
    """Return PK = IDEM#{idempotency_key}."""
    if not key:
        raise ValueError("idempotency key is required")
    return f"{IDEMPOTENCY_PK_PREFIX}{key}"


def deployment_pk(service: str) -> str:
    """Return PK = SERVICE#{service}."""
    return f"{SERVICE_PK_PREFIX}{_require_token(service, 'service')}"


def deployment_sk(deployed_at: datetime, version: str) -> str:
    """Return SK = DEPLOY#{timestamp}#{version}."""
    if not version:
        raise ValueError("version is required")
    if "#" in version:
        raise ValueError("version must not contain '#'")
    return f"{DEPLOY_SK_PREFIX}{utc_sort_timestamp(deployed_at)}#{version}"

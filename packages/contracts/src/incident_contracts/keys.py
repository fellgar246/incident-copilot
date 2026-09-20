"""Persistence key helpers. Formats are part of the product contract."""

from __future__ import annotations

from datetime import UTC, datetime

INCIDENT_PK_PREFIX = "INCIDENT#"
EVENT_SK_PREFIX = "EVENT#"


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

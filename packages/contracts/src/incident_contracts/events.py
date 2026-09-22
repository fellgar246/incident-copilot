"""Versioned incident.detected.v1 event contract used by ingest consumers."""

from __future__ import annotations

import json
from datetime import datetime
from importlib.resources import files
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from incident_contracts.enums import ActorKind, EventType, IncidentStatus, ScenarioId, Severity
from incident_contracts.errors import InvalidIncidentEventError, UnsupportedSchemaVersionError
from incident_contracts.models import Incident, IncidentEvent, IncidentFixture

SUPPORTED_SCHEMA_VERSION = "1"
INCIDENT_DETECTED_DETAIL_TYPE = "incident.detected.v1"
DEFAULT_EVENT_SOURCE = "ai-incident-copilot.incidents"
SCHEMA_RESOURCE = "schemas/incident.detected.v1.json"


class IncidentDetectedV1(BaseModel):
    """Ingest event. Unknown fields are ignored so producers can evolve forward."""

    model_config = ConfigDict(extra="ignore")

    schema_version: str
    event_id: str = Field(min_length=1)
    alarm_name: str = Field(min_length=1)
    service: str = Field(min_length=1)
    severity: Severity
    occurred_at: datetime
    correlation_id: str = Field(min_length=1)
    scenario: ScenarioId
    incident_id: str | None = Field(default=None, min_length=1)
    simulation_id: str | None = Field(default=None, min_length=1)


def incident_detected_v1_schema() -> dict[str, Any]:
    """Return the published JSON Schema document for incident.detected.v1."""
    resource = files("incident_contracts").joinpath(SCHEMA_RESOURCE)
    loaded: Any = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError("incident.detected.v1 schema must be a JSON object")
    return loaded


def parse_incident_detected(payload: Any) -> IncidentDetectedV1:
    """Validate a detected-incident event. Higher schema versions raise explicitly."""
    if not isinstance(payload, dict):
        raise InvalidIncidentEventError("incident.detected payload must be an object")
    version = payload.get("schema_version")
    if version is None or version == "":
        raise UnsupportedSchemaVersionError("schema_version is required")
    version_text = str(version)
    if version_text != SUPPORTED_SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(
            f"unsupported schema_version: {version}; supported: {SUPPORTED_SCHEMA_VERSION}"
        )
    try:
        return IncidentDetectedV1.model_validate(payload)
    except ValidationError as exc:
        raise InvalidIncidentEventError(str(exc)) from exc


def incident_id_for_event(event_id: str) -> str:
    """Stable incident_id derived from event_id when the producer omitted one."""
    if event_id.startswith("evt_"):
        return f"inc_{event_id.removeprefix('evt_')}"
    return f"inc_{event_id}"


def detected_event_from_fixture(fixture: IncidentFixture) -> IncidentDetectedV1:
    """Map a simulator fixture onto the ingest event that workers consume."""
    incident = fixture.incident
    if not incident.source_event_id:
        raise ValueError("fixture incident is missing source_event_id")
    return IncidentDetectedV1(
        schema_version=SUPPORTED_SCHEMA_VERSION,
        event_id=incident.source_event_id,
        alarm_name=incident.alarm_name,
        service=incident.service,
        severity=incident.severity,
        occurred_at=incident.started_at,
        correlation_id=incident.correlation_id,
        scenario=fixture.scenario,
        incident_id=incident.incident_id,
        simulation_id=incident.simulation_id,
    )


def incident_from_detected(event: IncidentDetectedV1) -> tuple[Incident, IncidentEvent]:
    """Build the DETECTED incident and ALARM_RECEIVED row for an ingest event."""
    incident_id = event.incident_id or incident_id_for_event(event.event_id)
    incident = Incident(
        incident_id=incident_id,
        service=event.service,
        severity=event.severity,
        status=IncidentStatus.DETECTED,
        alarm_name=event.alarm_name,
        started_at=event.occurred_at,
        updated_at=event.occurred_at,
        correlation_id=event.correlation_id,
        simulation_id=event.simulation_id,
        source_event_id=event.event_id,
    )
    alarm = IncidentEvent(
        event_id=event.event_id,
        incident_id=incident_id,
        event_type=EventType.ALARM_RECEIVED,
        timestamp=event.occurred_at,
        actor=ActorKind.SYSTEM.value,
        payload={
            "alarm_name": event.alarm_name,
            "scenario": event.scenario.value,
            "schema_version": event.schema_version,
            "correlation_id": event.correlation_id,
        },
        from_status=None,
        to_status=IncidentStatus.DETECTED,
    )
    return incident, alarm

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from incident_contracts.enums import ScenarioId, Severity
from incident_contracts.errors import InvalidIncidentEventError, UnsupportedSchemaVersionError
from incident_contracts.events import (
    INCIDENT_DETECTED_DETAIL_TYPE,
    SUPPORTED_SCHEMA_VERSION,
    detected_event_from_fixture,
    incident_detected_v1_schema,
    incident_from_detected,
    parse_incident_detected,
)
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from simulator import simulate

REQUIRED_FIELDS = (
    "schema_version",
    "event_id",
    "alarm_name",
    "service",
    "severity",
    "occurred_at",
    "correlation_id",
    "scenario",
)

VALID_EVENT: dict[str, Any] = {
    "schema_version": "1",
    "event_id": "evt_payments_1",
    "alarm_name": "payments-5xx-rate",
    "service": "payments-api",
    "severity": "HIGH",
    "occurred_at": "2026-09-20T14:00:00.000Z",
    "correlation_id": "cor_trace_1",
    "scenario": "deployment_regression",
}


def _validator() -> Draft202012Validator:
    return Draft202012Validator(
        incident_detected_v1_schema(),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def test_published_schema_covers_required_ingest_fields() -> None:
    schema = incident_detected_v1_schema()
    assert schema["title"] == INCIDENT_DETECTED_DETAIL_TYPE
    assert schema["additionalProperties"] is True
    assert schema["properties"]["schema_version"]["const"] == SUPPORTED_SCHEMA_VERSION
    assert set(schema["required"]) == set(REQUIRED_FIELDS)


def test_json_schema_accepts_unknown_fields() -> None:
    payload = {**VALID_EVENT, "cloudwatch_alarm_arn": "arn:aws:cloudwatch:example"}
    _validator().validate(payload)
    parsed = parse_incident_detected(payload)
    assert parsed.event_id == "evt_payments_1"
    assert not hasattr(parsed, "cloudwatch_alarm_arn")


def test_json_schema_rejects_missing_required_field() -> None:
    payload = dict(VALID_EVENT)
    del payload["correlation_id"]
    with pytest.raises(ValidationError):
        _validator().validate(payload)


def test_consumer_rejects_unsupported_schema_version_explicitly() -> None:
    payload = {**VALID_EVENT, "schema_version": "2"}
    with pytest.raises(UnsupportedSchemaVersionError, match="unsupported schema_version: 2"):
        parse_incident_detected(payload)
    with pytest.raises(ValidationError):
        _validator().validate(payload)


def test_consumer_rejects_malformed_payload() -> None:
    with pytest.raises(InvalidIncidentEventError):
        parse_incident_detected("not-an-object")
    with pytest.raises(InvalidIncidentEventError):
        parse_incident_detected({**VALID_EVENT, "event_id": ""})


def test_fixture_round_trip_preserves_correlation_id() -> None:
    fixture = simulate(ScenarioId.DEPLOYMENT_REGRESSION, seed="schema")
    event = detected_event_from_fixture(fixture)
    parsed = parse_incident_detected(event.model_dump(mode="json"))
    incident, alarm = incident_from_detected(parsed)
    assert incident.source_event_id == event.event_id
    assert incident.correlation_id == fixture.incident.correlation_id
    assert incident.correlation_id == alarm.payload["correlation_id"]
    assert incident.severity is Severity.HIGH
    assert incident.started_at == datetime(2026, 9, 20, 14, 0, tzinfo=UTC)

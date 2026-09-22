from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from cost_guardrails.envfile import parse_env_file
from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import load_quotas
from incident_contracts.enums import ScenarioId
from incident_contracts.events import detected_event_from_fixture, parse_incident_detected
from incident_contracts.repository import InMemoryIncidentRepository
from incident_worker.envelope import unwrap_sqs_body
from incident_worker.handler import handle_records
from incident_worker.processor import ingest_detected

from simulator import simulate

ENV_EXAMPLE = parse_env_file(Path(__file__).resolve().parents[3] / ".env.example")


def _sqs_event(body: dict[str, Any] | str, message_id: str = "msg-1") -> dict[str, Any]:
    payload = body if isinstance(body, str) else json.dumps(body)
    return {
        "Records": [
            {
                "messageId": message_id,
                "receiptHandle": "handle-1",
                "body": payload,
                "attributes": {"ApproximateReceiveCount": "1"},
                "eventSource": "aws:sqs",
            }
        ]
    }


def _detected_payload(seed: str = "worker", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    fixture = simulate(ScenarioId.DEPLOYMENT_REGRESSION, seed=seed)
    event = detected_event_from_fixture(fixture)
    payload = event.model_dump(mode="json")
    if extra:
        payload.update(extra)
    return payload


def test_unwrap_eventbridge_envelope() -> None:
    detail = _detected_payload()
    wrapped = {
        "version": "0",
        "id": "eb-1",
        "detail-type": "incident.detected.v1",
        "source": "ai-incident-copilot.incidents",
        "detail": detail,
    }
    assert unwrap_sqs_body(json.dumps(wrapped))["event_id"] == detail["event_id"]
    assert unwrap_sqs_body(json.dumps(detail))["event_id"] == detail["event_id"]


def test_one_event_creates_one_incident_with_correlation_id() -> None:
    repository = InMemoryIncidentRepository()
    payload = _detected_payload("happy")
    result = handle_records(_sqs_event(payload), repository=repository)
    assert result == {"batchItemFailures": []}
    incidents = repository.list_incidents()
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident.source_event_id == payload["event_id"]
    assert incident.correlation_id == payload["correlation_id"]
    events = repository.list_events(incident.incident_id)
    assert events[0].payload["correlation_id"] == payload["correlation_id"]


def test_duplicate_event_id_does_not_create_second_incident() -> None:
    repository = InMemoryIncidentRepository()
    payload = _detected_payload("dup")
    first = handle_records(_sqs_event(payload, "msg-a"), repository=repository)
    second = handle_records(_sqs_event(payload, "msg-b"), repository=repository)
    assert first == second == {"batchItemFailures": []}
    assert len(repository.list_incidents()) == 1
    event = parse_incident_detected(payload)
    replay = ingest_detected(event, repository=repository)
    assert replay.incident_id == repository.list_incidents()[0].incident_id


def test_unknown_fields_are_ignored_on_ingest() -> None:
    repository = InMemoryIncidentRepository()
    payload = _detected_payload("fwd", extra={"producer_build": "2026.09.20"})
    result = handle_records(_sqs_event(payload), repository=repository)
    assert result["batchItemFailures"] == []
    assert len(repository.list_incidents()) == 1


def test_unsupported_schema_version_is_failed_for_dlq() -> None:
    repository = InMemoryIncidentRepository()
    payload = _detected_payload("poison")
    payload["schema_version"] = "2"
    result = handle_records(_sqs_event(payload, "poison-1"), repository=repository)
    assert result == {"batchItemFailures": [{"itemIdentifier": "poison-1"}]}
    assert repository.list_incidents() == []


def test_malformed_body_is_failed_for_dlq() -> None:
    repository = InMemoryIncidentRepository()
    result = handle_records(_sqs_event("not-json", "poison-2"), repository=repository)
    assert result == {"batchItemFailures": [{"itemIdentifier": "poison-2"}]}
    assert repository.list_incidents() == []


def test_eventbridge_wrapped_record_ingests() -> None:
    repository = InMemoryIncidentRepository()
    detail = _detected_payload("wrap")
    wrapped = {
        "detail-type": "incident.detected.v1",
        "source": "ai-incident-copilot.incidents",
        "detail": detail,
    }
    result = handle_records(_sqs_event(wrapped), repository=repository)
    assert result["batchItemFailures"] == []
    assert repository.list_incidents()[0].correlation_id == detail["correlation_id"]


def test_quota_blocks_new_incidents_not_replays() -> None:
    repository = InMemoryIncidentRepository()
    quotas = replace(load_quotas(ENV_EXAMPLE), max_incidents_per_day=1)
    first = handle_records(
        _sqs_event(_detected_payload("quota-a"), "m1"),
        repository=repository,
        quotas=quotas,
    )
    replay = handle_records(
        _sqs_event(_detected_payload("quota-a"), "m2"),
        repository=repository,
        quotas=quotas,
    )
    second = handle_records(
        _sqs_event(_detected_payload("quota-b"), "m3"),
        repository=repository,
        quotas=quotas,
    )
    assert first["batchItemFailures"] == []
    assert replay["batchItemFailures"] == []
    assert second == {"batchItemFailures": [{"itemIdentifier": "m3"}]}
    assert len(repository.list_incidents()) == 1
    with pytest.raises(QuotaExceededError):
        ingest_detected(
            parse_incident_detected(_detected_payload("quota-c")),
            repository=repository,
            quotas=quotas,
        )

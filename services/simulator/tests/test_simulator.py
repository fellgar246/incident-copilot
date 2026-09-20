from __future__ import annotations

from pathlib import Path

import pytest
from incident_contracts.enums import ScenarioId
from incident_contracts.repository import InMemoryIncidentRepository
from incident_contracts.service import IncidentService
from incident_contracts.surface import DEMO_SERVICES
from simulator.catalog import SPECS

from simulator import simulate

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "incidents"
DESTRUCTIVE_HINTS = ("delete", "destroy", "terminate", "drop table", "force-reset")


@pytest.mark.parametrize("scenario", list(ScenarioId))
def test_same_seed_is_byte_stable(scenario: ScenarioId) -> None:
    left = simulate(scenario, seed="golden")
    right = simulate(scenario, seed="golden")
    assert left.model_dump(mode="json") == right.model_dump(mode="json")


@pytest.mark.parametrize("scenario", list(ScenarioId))
def test_golden_fixture_snapshot(scenario: ScenarioId) -> None:
    fixture = simulate(scenario, seed="golden")
    path = FIXTURES / f"{scenario.value}.json"
    assert path.exists(), f"missing golden fixture {path}"
    assert fixture.model_dump_json(indent=2) + "\n" == path.read_text(encoding="utf-8")


def test_scenarios_use_demo_services() -> None:
    assert {spec.service for spec in SPECS.values()} <= set(DEMO_SERVICES)


def test_deployment_regression_has_required_evidence() -> None:
    fixture = simulate(ScenarioId.DEPLOYMENT_REGRESSION, seed="golden")
    payload_blob = fixture.model_dump_json()
    assert "UPSTREAM_TIMEOUT" in payload_blob
    assert "2026.09.20.3" in payload_blob
    assert fixture.incident.service == "payments-api"
    assert fixture.expected_diagnosis.confidence >= 0.85
    assert fixture.expected_diagnosis.requires_approval is True
    sources = {item.source for item in fixture.evidence}
    assert "cloudwatch.logs" in sources
    assert "deployments" in sources
    assert "knowledge.runbooks" in sources


def test_pool_scenario_does_not_blame_cpu() -> None:
    fixture = simulate(ScenarioId.CONNECTION_POOL_EXHAUSTION, seed="golden")
    assert "POOL_EXHAUSTED" in fixture.model_dump_json()
    assert "CPU saturation" in fixture.expected_diagnosis.alternative_hypotheses
    assert "pool" in fixture.expected_diagnosis.probable_cause.lower()


def test_queue_backlog_points_at_consumer() -> None:
    fixture = simulate(ScenarioId.QUEUE_BACKLOG, seed="golden")
    blob = fixture.model_dump_json()
    assert "ApproximateNumberOfMessagesVisible" in blob
    assert "ApproximateAgeOfOldestMessage" in blob
    assert "consumer bottleneck" in fixture.expected_diagnosis.summary.lower()
    assert fixture.incident.service == "notifications-worker"
    assert fixture.expected_diagnosis.destructive is False
    assert "concurrency" in fixture.expected_diagnosis.recommended_action.lower()


def test_false_positive_is_not_destructive() -> None:
    fixture = simulate(ScenarioId.FALSE_POSITIVE, seed="golden")
    action = fixture.expected_diagnosis.recommended_action.lower()
    assert fixture.expected_diagnosis.confidence < 0.5
    assert fixture.expected_diagnosis.destructive is False
    assert fixture.expected_diagnosis.requires_approval is False
    assert not any(hint in action for hint in DESTRUCTIVE_HINTS)
    assert "do not remediate" in action


def test_different_seeds_change_ids() -> None:
    left = simulate(ScenarioId.QUEUE_BACKLOG, seed="a")
    right = simulate(ScenarioId.QUEUE_BACKLOG, seed="b")
    assert left.incident.incident_id != right.incident.incident_id


def test_fixture_ingests_idempotently_in_memory() -> None:
    fixture = simulate(ScenarioId.DEPLOYMENT_REGRESSION, seed="golden")
    service = IncidentService(InMemoryIncidentRepository())
    first = service.ingest_fixture(fixture)
    second = service.ingest_fixture(fixture)
    queued = service.queue(
        first.incident_id,
        actor="system",
        at=fixture.incident.started_at,
        event_id=f"{fixture.events[0].event_id}-queued",
    )
    assert first.incident_id == second.incident_id
    assert len(service.list_incidents()) == 1
    assert queued.status.value == "QUEUED"
    events = service.events(first.incident_id)
    event_ids = {item.event_id for item in events}
    expected_ids = {item.event_id for item in fixture.events}
    expected_ids.add(f"{fixture.events[0].event_id}-queued")
    assert event_ids == expected_ids
    assert any(item.event_type.value == "ALARM_RECEIVED" for item in events)
    assert any(item.event_type.value == "EVIDENCE_ADDED" for item in events)

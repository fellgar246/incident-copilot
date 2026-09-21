from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from api.deps import build_container
from api.main import create_app
from api.persistence.deployments import InMemoryDeploymentRepository
from api.settings import Settings
from cost_guardrails.envfile import parse_env_file
from cost_guardrails.quotas import load_quotas
from fastapi.testclient import TestClient
from incident_contracts.enums import IncidentStatus, ScenarioId
from incident_contracts.repository import InMemoryIncidentRepository

ENV_EXAMPLE = parse_env_file(Path(__file__).resolve().parents[3] / ".env.example")


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "x-request-id" in response.headers
    assert "x-correlation-id" in response.headers


def test_health_aws_memory(client: TestClient) -> None:
    response = client.get("/health/aws")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["repository"] == "memory"


def test_simulate_create_get_and_ordered_timeline(client: TestClient) -> None:
    created = client.post(
        "/incidents/simulate",
        json={"scenario": ScenarioId.DEPLOYMENT_REGRESSION.value, "seed": "api-test"},
    )
    assert created.status_code == 201
    incident = created.json()
    incident_id = incident["incident_id"]
    assert incident["service"] == "payments-api"
    assert incident["status"] == IncidentStatus.DETECTED.value

    fetched = client.get(f"/incidents/{incident_id}")
    assert fetched.status_code == 200
    assert fetched.json()["incident_id"] == incident_id

    events = client.get(f"/incidents/{incident_id}/events")
    assert events.status_code == 200
    timeline = events.json()
    assert timeline
    timestamps = [item["timestamp"] for item in timeline]
    assert timestamps == sorted(timestamps)
    assert any(item["event_type"] == "ALARM_RECEIVED" for item in timeline)


def test_simulate_replay_returns_200_without_duplicate(client: TestClient) -> None:
    payload = {"scenario": ScenarioId.QUEUE_BACKLOG.value, "seed": "replay"}
    first = client.post("/incidents/simulate", json=payload)
    second = client.post("/incidents/simulate", json=payload)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["incident_id"] == second.json()["incident_id"]
    listed = client.get("/incidents")
    assert listed.status_code == 200
    matches = [item for item in listed.json() if item["incident_id"] == first.json()["incident_id"]]
    assert len(matches) == 1


def test_idempotency_key_replay(client: TestClient) -> None:
    headers = {"Idempotency-Key": "demo-key-1"}
    first = client.post(
        "/incidents/simulate",
        json={"scenario": ScenarioId.FALSE_POSITIVE.value, "seed": "idemp-a"},
        headers=headers,
    )
    second = client.post(
        "/incidents/simulate",
        json={"scenario": ScenarioId.CONNECTION_POOL_EXHAUSTION.value, "seed": "idemp-b"},
        headers=headers,
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["incident_id"] == second.json()["incident_id"]


def test_list_filters_by_status_and_service(client: TestClient) -> None:
    client.post(
        "/incidents/simulate",
        json={"scenario": ScenarioId.DEPLOYMENT_REGRESSION.value, "seed": "flt-a"},
    )
    client.post(
        "/incidents/simulate",
        json={"scenario": ScenarioId.QUEUE_BACKLOG.value, "seed": "flt-b"},
    )
    filtered = client.get("/incidents", params={"service": "payments-api", "status": "DETECTED"})
    assert filtered.status_code == 200
    items = filtered.json()
    assert items
    assert all(item["service"] == "payments-api" for item in items)
    assert all(item["status"] == "DETECTED" for item in items)
    started = [item["started_at"] for item in client.get("/incidents").json()]
    assert started == sorted(started, reverse=True)


def test_unknown_incident_is_404(client: TestClient) -> None:
    assert client.get("/incidents/inc_missing").status_code == 404
    assert client.get("/incidents/inc_missing/events").status_code == 404


def test_invalid_payload_is_422(client: TestClient) -> None:
    response = client.post("/incidents/simulate", json={"scenario": "not-a-scenario"})
    assert response.status_code == 422
    extra = client.post(
        "/incidents/simulate",
        json={"scenario": ScenarioId.FALSE_POSITIVE.value, "unexpected": True},
    )
    assert extra.status_code == 422
    bad_status = client.get("/incidents", params={"status": "NOPE"})
    assert bad_status.status_code == 422


def test_unimplemented_routes_are_501(client: TestClient) -> None:
    assert client.post("/incidents/inc_x/investigate").status_code == 501
    assert client.get("/metrics/costs").status_code == 501
    assert client.get("/evaluations").status_code == 501


def test_daily_quota_blocks_new_incidents_not_replays(
    settings: Settings,
    repository: InMemoryIncidentRepository,
    deployments: InMemoryDeploymentRepository,
) -> None:
    quotas = replace(load_quotas(ENV_EXAMPLE), max_incidents_per_day=1)
    client = TestClient(
        create_app(
            container=build_container(
                settings=settings,
                store=repository,
                deployments=deployments,
                quotas=quotas,
            )
        )
    )
    first = client.post(
        "/incidents/simulate",
        json={"scenario": ScenarioId.FALSE_POSITIVE.value, "seed": "quota-a"},
    )
    replay = client.post(
        "/incidents/simulate",
        json={"scenario": ScenarioId.FALSE_POSITIVE.value, "seed": "quota-a"},
    )
    second = client.post(
        "/incidents/simulate",
        json={"scenario": ScenarioId.FALSE_POSITIVE.value, "seed": "quota-b"},
    )
    assert first.status_code == 201
    assert replay.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"]["stop_reason"] == "COST_OR_USAGE_GUARDRAIL"


def test_propagates_incoming_correlation_headers(client: TestClient) -> None:
    response = client.get(
        "/health",
        headers={"x-request-id": "req-fixed", "x-correlation-id": "cor-fixed"},
    )
    assert response.headers["x-request-id"] == "req-fixed"
    assert response.headers["x-correlation-id"] == "cor-fixed"

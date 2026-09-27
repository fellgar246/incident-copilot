from __future__ import annotations

from datetime import UTC, datetime, timedelta

import boto3
import pytest
from api.persistence.mapping import deployment_item
from deployments_tool.errors import ToolRetriesExhausted, ToolValidationError, TransientToolError
from deployments_tool.limits import ToolLimits
from deployments_tool.store import DynamoDeploymentStore, MemoryDeploymentStore
from deployments_tool.tools import REQUIRES_APPROVAL, TOOL_CLASS, get_recent_deployments
from incident_contracts.enums import ScenarioId
from incident_contracts.models import Deployment
from moto import mock_aws

from simulator import seed_fixture, simulate

pytestmark = pytest.mark.integration

LIMITS = ToolLimits()
REGION = "us-east-1"


def _now(fixture_start: datetime) -> datetime:
    return fixture_start + timedelta(minutes=10)


def test_schema_rejects_unknown_service_and_wide_lookback() -> None:
    store = MemoryDeploymentStore()
    with pytest.raises(ToolValidationError):
        get_recent_deployments(
            {"service": "payments-api", "lookback_hours": 24, "query": "scan *"},
            store=store,
            limits=LIMITS,
        )
    with pytest.raises(ToolValidationError):
        get_recent_deployments(
            {"service": "prod-admin", "lookback_hours": 24},
            store=store,
            limits=LIMITS,
        )
    with pytest.raises(ToolValidationError):
        get_recent_deployments(
            {"service": "payments-api", "lookback_hours": 73},
            store=store,
            limits=LIMITS,
        )
    assert TOOL_CLASS.value == "READ_ONLY"
    assert REQUIRES_APPROVAL is False


def test_fixtures_return_the_expected_releases() -> None:
    regression = simulate(ScenarioId.DEPLOYMENT_REGRESSION, seed="golden")
    store = MemoryDeploymentStore()
    seed_fixture(regression, logs=_Sink(), metrics=_Sink(), deployments=store)
    seed_fixture(regression, logs=_Sink(), metrics=_Sink(), deployments=store)
    result = get_recent_deployments(
        {"service": "payments-api", "lookback_hours": 24},
        store=store,
        now=_now(regression.incident.started_at),
        limits=LIMITS,
    )
    assert result.untrusted is True
    assert result.redacted is True
    assert [item.version for item in result.items] == ["2026.09.20.3", "2026.09.20.2"]
    assert result.truncated is False

    pool = simulate(ScenarioId.CONNECTION_POOL_EXHAUSTION, seed="golden")
    pool_store = MemoryDeploymentStore()
    seed_fixture(pool, logs=_Sink(), metrics=_Sink(), deployments=pool_store)
    hidden = get_recent_deployments(
        {"service": "orders-api", "lookback_hours": 24},
        store=pool_store,
        now=_now(pool.incident.started_at),
        limits=LIMITS,
    )
    assert hidden.items == []

    queue = simulate(ScenarioId.QUEUE_BACKLOG, seed="golden")
    queue_store = MemoryDeploymentStore()
    seed_fixture(queue, logs=_Sink(), metrics=_Sink(), deployments=queue_store)
    queued = get_recent_deployments(
        {"service": "notifications-worker", "lookback_hours": 24},
        store=queue_store,
        now=_now(queue.incident.started_at),
        limits=LIMITS,
    )
    assert queued.items[0].version == "2026.09.19.4"


def test_output_is_capped_at_five_and_summaries_are_redacted() -> None:
    store = MemoryDeploymentStore()
    origin = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
    for index in range(6):
        store.write_deployment(
            Deployment(
                service="payments-api",
                version=f"2026.09.21.{index}",
                commit_sha=f"{index:040x}",
                deployed_at=origin - timedelta(hours=index),
                change_summary="baseline" if index else "rotated token=super-secret-value",
            )
        )
    result = get_recent_deployments(
        {"service": "payments-api", "lookback_hours": 24},
        store=store,
        now=origin,
        limits=LIMITS,
    )
    assert len(result.items) == 5
    assert result.truncated is True
    assert result.items[0].version == "2026.09.21.0"
    blob = result.model_dump_json()
    assert "super-secret-value" not in blob
    assert "token=[REDACTED]" in blob


def test_timeout_and_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MemoryDeploymentStore()

    def boom(**kwargs: object) -> list[Deployment]:
        del kwargs
        raise TransientToolError("throttle")

    monkeypatch.setattr(store, "query", boom)
    with pytest.raises(ToolRetriesExhausted):
        get_recent_deployments(
            {"service": "payments-api", "lookback_hours": 1},
            store=store,
            limits=ToolLimits(max_attempts=2),
        )


@mock_aws
def test_dynamodb_reader_matches_api_deployment_items() -> None:
    client = boto3.client("dynamodb", region_name=REGION)
    client.create_table(
        TableName="deployments",
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
    table = boto3.resource("dynamodb", region_name=REGION).Table("deployments")
    fixture = simulate(ScenarioId.DEPLOYMENT_REGRESSION, seed="golden")
    for deployment in fixture.deployments:
        table.put_item(Item=deployment_item(deployment, expires_at=2_000_000_000))
    store = DynamoDeploymentStore(table)
    result = get_recent_deployments(
        {"service": "payments-api", "lookback_hours": 24},
        store=store,
        now=_now(fixture.incident.started_at),
        limits=LIMITS,
    )
    assert result.items[0].version == "2026.09.20.3"
    assert result.items[0].commit_sha.startswith("a1b2c3d4")


class _Sink:
    def write_log(self, sample: object) -> None:
        del sample

    def write_metric(self, sample: object) -> None:
        del sample

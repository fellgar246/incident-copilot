from __future__ import annotations

from datetime import UTC, datetime, timedelta

import boto3
import pytest
from cloudwatch_tool.cloudwatch import CloudWatchTelemetryStore
from cloudwatch_tool.limits import ToolLimits
from cloudwatch_tool.tools import query_logs, query_metrics
from incident_contracts.enums import ScenarioId
from incident_contracts.models import LogSample, MetricSample
from moto import mock_aws

from simulator import simulate

pytestmark = pytest.mark.integration

LIMITS = ToolLimits()
REGION = "us-east-1"
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


class _SpyLogs:
    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.calls: list[dict[str, object]] = []

    def filter_log_events(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        return self._inner.filter_log_events(**kwargs)  # type: ignore[attr-defined]

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


@mock_aws
def test_cloudwatch_round_trip_for_fixture_evidence() -> None:
    logs_client = boto3.client("logs", region_name=REGION)
    metrics_client = boto3.client("cloudwatch", region_name=REGION)
    spy = _SpyLogs(logs_client)
    store = CloudWatchTelemetryStore(
        logs_client=spy,
        metrics_client=metrics_client,
        project="ai-incident-copilot",
        environment="dev",
        namespace="AIIncidentCopilot/Demo",
    )
    fixture = simulate(ScenarioId.DEPLOYMENT_REGRESSION, seed="golden")
    shift = NOW - fixture.incident.started_at
    for sample in fixture.telemetry.logs:
        store.write_log(
            LogSample(
                timestamp=sample.timestamp + shift,
                service=sample.service,
                level=sample.level,
                message=sample.message,
                fields=sample.fields,
            )
        )
    for sample in fixture.telemetry.metrics:
        store.write_metric(
            MetricSample(
                timestamp=sample.timestamp + shift,
                service=sample.service,
                name=sample.name,
                value=sample.value,
                unit=sample.unit,
            )
        )
    moment = NOW + timedelta(minutes=10)
    logs = query_logs(
        {"service": "payments-api", "start_minutes_ago": 15, "level": "ERROR"},
        store=store,
        now=moment,
        limits=LIMITS,
    )
    metrics = query_metrics(
        {"service": "payments-api", "metric": "error_rate", "start_minutes_ago": 60},
        store=store,
        now=moment,
        limits=LIMITS,
    )
    assert any("UPSTREAM_TIMEOUT" in item.message for item in logs.items)
    assert logs.log_group == "/ai-incident-copilot/dev/payments-api"
    assert any(item.value == pytest.approx(8.4) for item in metrics.items)
    assert spy.calls
    for call in spy.calls:
        assert "filterPattern" not in call
        assert "queryString" not in call
        assert call["logGroupName"] == "/ai-incident-copilot/dev/payments-api"


@mock_aws
def test_missing_log_group_returns_no_rows() -> None:
    store = CloudWatchTelemetryStore(
        logs_client=boto3.client("logs", region_name=REGION),
        metrics_client=boto3.client("cloudwatch", region_name=REGION),
    )
    result = query_logs(
        {"service": "orders-api", "start_minutes_ago": 15, "level": "ERROR"},
        store=store,
        now=NOW,
        limits=LIMITS,
    )
    assert result.items == []

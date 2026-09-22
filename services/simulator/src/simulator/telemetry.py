"""Emit structured logs and metric points, and seed them into a telemetry sink."""

from __future__ import annotations

import json
from datetime import UTC
from typing import Any, Protocol

from incident_contracts.models import Deployment, IncidentFixture, LogSample, MetricSample


class LogSink(Protocol):
    def write_log(self, sample: LogSample) -> None: ...


class MetricSink(Protocol):
    def write_metric(self, sample: MetricSample) -> None: ...


class DeploymentSink(Protocol):
    def write_deployment(self, deployment: Deployment) -> None: ...


def structured_log_event(sample: LogSample) -> dict[str, Any]:
    """JSON object a demo service would write to its log group."""
    moment = sample.timestamp if sample.timestamp.tzinfo else sample.timestamp.replace(tzinfo=UTC)
    return {
        "timestamp": moment.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "service": sample.service,
        "level": sample.level,
        "message": sample.message,
        "fields": sample.fields,
    }


def emit_structured_logs(fixture: IncidentFixture) -> list[str]:
    """Return one JSON log line per sample in `fixture`."""
    return [
        json.dumps(structured_log_event(sample), separators=(",", ":"), default=str)
        for sample in fixture.telemetry.logs
    ]


def emit_metric_points(fixture: IncidentFixture) -> list[dict[str, Any]]:
    """Return compact metric points for the samples in `fixture`."""
    return [
        {
            "timestamp": sample.timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "service": sample.service,
            "name": sample.name,
            "value": sample.value,
            "unit": sample.unit,
        }
        for sample in fixture.telemetry.metrics
    ]


def seed_fixture(
    fixture: IncidentFixture,
    *,
    logs: LogSink,
    metrics: MetricSink,
    deployments: DeploymentSink,
) -> None:
    """Plant the fixture's logs, metrics, and deployments into the given sinks."""
    for log in fixture.telemetry.logs:
        logs.write_log(log)
    for point in fixture.telemetry.metrics:
        metrics.write_metric(point)
    for deployment in fixture.deployments:
        deployments.write_deployment(deployment)

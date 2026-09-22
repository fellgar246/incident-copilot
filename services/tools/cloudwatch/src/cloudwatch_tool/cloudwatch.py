"""CloudWatch Logs and metrics adapter constrained to the demo allowlist."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from incident_contracts.models import LogSample, MetricSample
from simulator.telemetry import structured_log_event

from cloudwatch_tool.allowlist import (
    DEFAULT_ENVIRONMENT,
    DEFAULT_METRIC_NAMESPACE,
    DEFAULT_PROJECT,
    SIGNALS,
    MetricName,
    canonical_metric,
    log_group_name,
    require_service,
)
from cloudwatch_tool.errors import AllowlistError, ToolError, TransientToolError
from cloudwatch_tool.store import as_utc

_STREAM = "fixture"
_PAGE_LIMIT = 3
_FETCH_LIMIT = 100
_THROTTLE_CODES = frozenset(
    {
        "ThrottlingException",
        "Throttling",
        "TooManyRequestsException",
        "RequestLimitExceeded",
    }
)
_UNITS = {
    "Count": "Count",
    "Percent": "Percent",
    "Milliseconds": "Milliseconds",
    "Seconds": "Seconds",
    "None": "None",
}


def _aws(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in _THROTTLE_CODES:
            raise TransientToolError(code) from exc
        raise ToolError(code or "cloudwatch request failed") from exc


class CloudWatchTelemetryStore:
    """Read allowlisted log groups and the demo metric namespace.

    `write_log` and `write_metric` exist so a seeder can plant fixture evidence.
    The read-only tool role is not granted those writes.
    """

    def __init__(
        self,
        *,
        logs_client: Any,
        metrics_client: Any,
        project: str = DEFAULT_PROJECT,
        environment: str = DEFAULT_ENVIRONMENT,
        namespace: str = DEFAULT_METRIC_NAMESPACE,
    ) -> None:
        self._logs = logs_client
        self._metrics = metrics_client
        self.project = project
        self.environment = environment
        self._namespace = namespace
        self._sequence_tokens: dict[tuple[str, str], str] = {}

    @classmethod
    def from_env(cls) -> CloudWatchTelemetryStore:
        """Build clients from the process environment."""
        region = os.environ.get("AWS_REGION", "us-east-1")
        return cls(
            logs_client=boto3.client("logs", region_name=region),
            metrics_client=boto3.client("cloudwatch", region_name=region),
            project=os.environ.get("TELEMETRY_PROJECT", DEFAULT_PROJECT),
            environment=os.environ.get("TELEMETRY_ENVIRONMENT", DEFAULT_ENVIRONMENT),
            namespace=os.environ.get("METRIC_NAMESPACE", DEFAULT_METRIC_NAMESPACE),
        )

    def write_log(self, sample: LogSample) -> None:
        group = log_group_name(sample.service, project=self.project, environment=self.environment)
        self._ensure_group(group)
        self._ensure_stream(group)
        message = json.dumps(structured_log_event(sample), separators=(",", ":"), default=str)
        event = {
            "timestamp": int(as_utc(sample.timestamp).timestamp() * 1000),
            "message": message,
        }
        kwargs: dict[str, Any] = {
            "logGroupName": group,
            "logStreamName": _STREAM,
            "logEvents": [event],
        }
        token = self._sequence_tokens.get((group, _STREAM))
        if token:
            kwargs["sequenceToken"] = token
        response = _aws(lambda: self._logs.put_log_events(**kwargs))
        next_token = response.get("nextSequenceToken")
        if isinstance(next_token, str) and next_token:
            self._sequence_tokens[(group, _STREAM)] = next_token

    def write_metric(self, sample: MetricSample) -> None:
        require_service(sample.service)
        canonical = canonical_metric(sample.name)
        if canonical is None:
            raise AllowlistError(f"metric signal is not allowlisted: {sample.name}")
        unit = _UNITS.get(sample.unit, "Count")
        _aws(
            lambda: self._metrics.put_metric_data(
                Namespace=self._namespace,
                MetricData=[
                    {
                        "MetricName": canonical.value,
                        "Dimensions": [
                            {"Name": "Service", "Value": sample.service},
                            {"Name": "Signal", "Value": sample.name},
                        ],
                        "Timestamp": as_utc(sample.timestamp),
                        "Value": float(sample.value),
                        "Unit": unit,
                    }
                ],
            )
        )

    def query_logs(
        self,
        *,
        service: str,
        start: datetime,
        end: datetime,
        level: str | None,
    ) -> list[LogSample]:
        group = log_group_name(service, project=self.project, environment=self.environment)
        start_ms = int(as_utc(start).timestamp() * 1000)
        end_ms = int(as_utc(end).timestamp() * 1000)
        events = self._filter_events(group, start_ms=start_ms, end_ms=end_ms)
        matched: list[LogSample] = []
        for event in events:
            sample = _parse_log_event(event, service)
            if sample is None:
                continue
            if level is not None and sample.level != level:
                continue
            matched.append(sample)
        matched.sort(key=lambda item: item.timestamp, reverse=True)
        return matched[:_FETCH_LIMIT]

    def query_metrics(
        self,
        *,
        service: str,
        metric: MetricName,
        start: datetime,
        end: datetime,
    ) -> list[MetricSample]:
        require_service(service)
        window_start = as_utc(start)
        window_end = as_utc(end)
        if window_end <= window_start:
            window_end = window_start + timedelta(seconds=1)
        found: dict[tuple[str, str, float], MetricSample] = {}
        dimension_sets: list[tuple[str, list[dict[str, str]]]] = [
            (metric.value, [{"Name": "Service", "Value": service}])
        ]
        for signal in SIGNALS[metric]:
            dimension_sets.append(
                (
                    signal,
                    [
                        {"Name": "Service", "Value": service},
                        {"Name": "Signal", "Value": signal},
                    ],
                )
            )
        for signal_name, dimensions in dimension_sets:
            datapoints = self._statistics(
                metric=metric,
                dimensions=dimensions,
                start=window_start,
                end=window_end,
            )
            for point in datapoints:
                timestamp = _point_time(point.get("Timestamp"))
                value = float(point.get("Average", 0.0))
                unit = str(point.get("Unit") or "Count")
                sample = MetricSample(
                    timestamp=timestamp,
                    service=service,
                    name=signal_name,
                    value=value,
                    unit=unit,
                )
                found[(timestamp.isoformat(), signal_name, value)] = sample
        return sorted(found.values(), key=lambda item: item.timestamp)

    def _filter_events(self, group: str, *, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        token: str | None = None
        for _ in range(_PAGE_LIMIT):
            kwargs: dict[str, Any] = {
                "logGroupName": group,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": _FETCH_LIMIT,
            }
            if token:
                kwargs["nextToken"] = token
            try:
                page = dict(kwargs)

                def read_page(bound: dict[str, Any] = page) -> Any:
                    return self._logs.filter_log_events(**bound)

                response = _aws(read_page)
            except ToolError as exc:
                if "ResourceNotFoundException" in str(exc):
                    return collected
                raise
            events = response.get("events") or []
            collected.extend(event for event in events if isinstance(event, dict))
            token = response.get("nextToken")
            if not token or len(collected) >= _FETCH_LIMIT:
                break
        return collected[:_FETCH_LIMIT]

    def _statistics(
        self,
        *,
        metric: MetricName,
        dimensions: list[dict[str, str]],
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        response = _aws(
            lambda: self._metrics.get_metric_statistics(
                Namespace=self._namespace,
                MetricName=metric.value,
                Dimensions=dimensions,
                StartTime=start,
                EndTime=end + timedelta(seconds=60),
                Period=60,
                Statistics=["Average"],
            )
        )
        datapoints = response.get("Datapoints") or []
        return [point for point in datapoints if isinstance(point, dict)]

    def _ensure_group(self, name: str) -> None:
        try:
            self._logs.create_log_group(logGroupName=name)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code != "ResourceAlreadyExistsException":
                raise ToolError(code or "create_log_group failed") from exc

    def _ensure_stream(self, group: str) -> None:
        try:
            self._logs.create_log_stream(logGroupName=group, logStreamName=_STREAM)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code != "ResourceAlreadyExistsException":
                raise ToolError(code or "create_log_stream failed") from exc


def _point_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    raise ToolError("metric datapoint is missing a timestamp")


def _parse_log_event(event: dict[str, Any], service: str) -> LogSample | None:
    raw_timestamp = event.get("timestamp")
    if not isinstance(raw_timestamp, int | float):
        return None
    timestamp = datetime.fromtimestamp(float(raw_timestamp) / 1000, tz=UTC)
    raw = str(event.get("message", ""))
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and "message" in payload:
        embedded = payload.get("service")
        if embedded not in (None, service):
            return None
        fields = payload.get("fields")
        return LogSample(
            timestamp=timestamp,
            service=service,
            level=str(payload.get("level") or "INFO"),
            message=str(payload["message"]),
            fields=fields if isinstance(fields, dict) else {},
        )
    return LogSample(timestamp=timestamp, service=service, level="INFO", message=raw, fields={})

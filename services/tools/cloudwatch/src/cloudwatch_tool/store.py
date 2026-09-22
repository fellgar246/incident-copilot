"""In-memory log and metric store used by local fixtures and tests."""

from __future__ import annotations

from datetime import UTC, datetime

from incident_contracts.models import LogSample, MetricSample

from cloudwatch_tool.allowlist import MetricName, canonical_metric, require_service
from cloudwatch_tool.errors import AllowlistError

_HARD_CAP = 1000


def as_utc(moment: datetime) -> datetime:
    """Normalize an aware timestamp to UTC."""
    if moment.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return moment.astimezone(UTC)


class InMemoryTelemetryStore:
    """Idempotent fixture store. Re-seeding the same sample does not duplicate it."""

    def __init__(self) -> None:
        self._logs: dict[tuple[str, str, str, str], LogSample] = {}
        self._metrics: dict[tuple[str, str, str, str, float], MetricSample] = {}

    def write_log(self, sample: LogSample) -> None:
        require_service(sample.service)
        key = (sample.service, as_utc(sample.timestamp).isoformat(), sample.level, sample.message)
        self._logs[key] = sample.model_copy(deep=True)

    def write_metric(self, sample: MetricSample) -> None:
        require_service(sample.service)
        if canonical_metric(sample.name) is None:
            raise AllowlistError(f"metric signal is not allowlisted: {sample.name}")
        key = (
            sample.service,
            as_utc(sample.timestamp).isoformat(),
            sample.name,
            sample.unit,
            float(sample.value),
        )
        self._metrics[key] = sample.model_copy(deep=True)

    def query_logs(
        self,
        *,
        service: str,
        start: datetime,
        end: datetime,
        level: str | None,
    ) -> list[LogSample]:
        require_service(service)
        window_start = as_utc(start)
        window_end = as_utc(end)
        matched = [
            item.model_copy(deep=True)
            for item in self._logs.values()
            if item.service == service
            and window_start <= as_utc(item.timestamp) <= window_end
            and (level is None or item.level == level)
        ]
        matched.sort(key=lambda item: item.timestamp, reverse=True)
        return matched[:_HARD_CAP]

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
        matched = [
            item.model_copy(deep=True)
            for item in self._metrics.values()
            if item.service == service
            and canonical_metric(item.name) is metric
            and window_start <= as_utc(item.timestamp) <= window_end
        ]
        matched.sort(key=lambda item: item.timestamp)
        return matched[:_HARD_CAP]

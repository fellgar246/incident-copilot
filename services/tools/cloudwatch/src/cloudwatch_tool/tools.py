"""query_logs and query_metrics.

Returned payloads are untrusted data. Callers must not treat log text as instructions.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import STOP_REASON
from incident_contracts.enums import ToolClass
from incident_contracts.models import LogSample, MetricSample
from observability.logging import current_context

from cloudwatch_tool.allowlist import (
    DEFAULT_ENVIRONMENT,
    DEFAULT_PROJECT,
    MetricName,
    log_group_name,
    require_metric,
    require_service,
)
from cloudwatch_tool.limits import ToolLimits
from cloudwatch_tool.models import (
    LogEvidenceItem,
    QueryLogsInput,
    QueryLogsResult,
    QueryMetricsInput,
    QueryMetricsResult,
)
from cloudwatch_tool.runtime import bounded_call
from cloudwatch_tool.sanitize import fit_items, redact_text, redact_value
from cloudwatch_tool.schemas import (
    parse_model,
    query_logs_input_schema,
    query_logs_output_schema,
    query_metrics_input_schema,
    query_metrics_output_schema,
    validate_output,
)

LOGGER = logging.getLogger("cloudwatch_tool")
TOOL_CLASS = ToolClass.READ_ONLY
REQUIRES_APPROVAL = False


class TelemetryReader(Protocol):
    def query_logs(
        self,
        *,
        service: str,
        start: datetime,
        end: datetime,
        level: str | None,
    ) -> list[LogSample]: ...

    def query_metrics(
        self,
        *,
        service: str,
        metric: MetricName,
        start: datetime,
        end: datetime,
    ) -> list[MetricSample]: ...


class CloudWatchTools:
    """Read-only log and metric tools over a local store or CloudWatch."""

    def __init__(
        self,
        store: TelemetryReader,
        *,
        limits: ToolLimits | None = None,
        project: str | None = None,
        environment: str | None = None,
    ) -> None:
        self._store = store
        self._limits = limits or ToolLimits.from_env()
        self._project = project or str(
            getattr(store, "project", None) or os.environ.get("TELEMETRY_PROJECT", DEFAULT_PROJECT)
        )
        self._environment = environment or str(
            getattr(store, "environment", None)
            or os.environ.get("TELEMETRY_ENVIRONMENT", DEFAULT_ENVIRONMENT)
        )

    def query_logs(
        self,
        payload: Any,
        *,
        now: datetime | None = None,
        calls_used: int | None = None,
    ) -> QueryLogsResult:
        request = parse_model(payload, query_logs_input_schema(self._limits), QueryLogsInput)
        assert isinstance(request, QueryLogsInput)
        require_service(request.service)
        self._enforce_budget(calls_used)
        end = _now(now)
        start = end - timedelta(minutes=request.start_minutes_ago)
        level = request.level.value if request.level is not None else None
        rows = bounded_call(
            lambda: self._store.query_logs(
                service=request.service,
                start=start,
                end=end,
                level=level,
            ),
            timeout_seconds=self._limits.timeout_seconds,
            attempts=self._limits.max_attempts,
        )
        rows.sort(key=lambda item: item.timestamp, reverse=True)
        truncated = len(rows) > request.limit
        selected = list(reversed(rows[: request.limit]))
        items = [_log_item(sample) for sample in selected]
        group = log_group_name(
            request.service, project=self._project, environment=self._environment
        )

        def build(chosen: list[LogEvidenceItem], was_truncated: bool) -> QueryLogsResult:
            return QueryLogsResult(
                service=request.service,
                log_group=group,
                window_minutes=request.start_minutes_ago,
                redacted=True,
                truncated=was_truncated,
                items=chosen,
            )

        result = fit_items(
            items,
            already_truncated=truncated,
            max_bytes=self._limits.max_output_bytes,
            build=build,
        )
        validate_output(result, query_logs_output_schema())
        _log_completion("query_logs", request.service, len(result.items), result.truncated)
        return result

    def query_metrics(
        self,
        payload: Any,
        *,
        now: datetime | None = None,
        calls_used: int | None = None,
    ) -> QueryMetricsResult:
        request = parse_model(payload, query_metrics_input_schema(self._limits), QueryMetricsInput)
        assert isinstance(request, QueryMetricsInput)
        require_service(request.service)
        metric = require_metric(request.metric.value)
        self._enforce_budget(calls_used)
        end = _now(now)
        start = end - timedelta(minutes=request.start_minutes_ago)
        rows = bounded_call(
            lambda: self._store.query_metrics(
                service=request.service,
                metric=metric,
                start=start,
                end=end,
            ),
            timeout_seconds=self._limits.timeout_seconds,
            attempts=self._limits.max_attempts,
        )
        items = [_metric_item(sample) for sample in rows]

        def build(chosen: list[Any], was_truncated: bool) -> QueryMetricsResult:
            return QueryMetricsResult(
                service=request.service,
                metric=metric,
                window_minutes=request.start_minutes_ago,
                redacted=True,
                truncated=was_truncated,
                items=chosen,
            )

        result = fit_items(
            items,
            already_truncated=False,
            max_bytes=self._limits.max_output_bytes,
            build=build,
        )
        validate_output(result, query_metrics_output_schema())
        _log_completion("query_metrics", request.service, len(result.items), result.truncated)
        return result

    def _enforce_budget(self, calls_used: int | None) -> None:
        if calls_used is None:
            return
        limit = self._limits.max_tool_calls_per_run
        if calls_used >= limit:
            raise QuotaExceededError(
                f"Quota MAX_TOOL_CALLS_PER_RUN reached ({calls_used}/{limit})",
                quota_name="MAX_TOOL_CALLS_PER_RUN",
                stop_reason=STOP_REASON,
            )


def query_logs(
    payload: Any,
    *,
    store: TelemetryReader,
    now: datetime | None = None,
    limits: ToolLimits | None = None,
    calls_used: int | None = None,
    project: str | None = None,
    environment: str | None = None,
) -> QueryLogsResult:
    """Validate `payload` and return redacted log evidence for one demo service."""
    return CloudWatchTools(
        store, limits=limits, project=project, environment=environment
    ).query_logs(payload, now=now, calls_used=calls_used)


def query_metrics(
    payload: Any,
    *,
    store: TelemetryReader,
    now: datetime | None = None,
    limits: ToolLimits | None = None,
    calls_used: int | None = None,
    project: str | None = None,
    environment: str | None = None,
) -> QueryMetricsResult:
    """Validate `payload` and return one declared metric for one demo service."""
    return CloudWatchTools(
        store, limits=limits, project=project, environment=environment
    ).query_metrics(payload, now=now, calls_used=calls_used)


def _now(moment: datetime | None) -> datetime:
    if moment is None:
        return datetime.now(UTC)
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return moment.astimezone(UTC)


def _log_item(sample: LogSample) -> LogEvidenceItem:
    fields = redact_value(sample.fields)
    if not isinstance(fields, dict):
        fields = {}
    return LogEvidenceItem(
        timestamp=sample.timestamp,
        level=sample.level,
        message=redact_text(sample.message),
        fields=fields,
    )


def _metric_item(sample: MetricSample) -> Any:
    from cloudwatch_tool.models import MetricEvidenceItem

    return MetricEvidenceItem(
        timestamp=sample.timestamp,
        name=redact_text(sample.name),
        value=float(sample.value),
        unit=sample.unit,
    )


def _log_completion(tool: str, service: str, items: int, truncated: bool) -> None:
    LOGGER.info(
        "tool.completed",
        extra={
            "fields": {
                "tool": tool,
                "service": service,
                "items": items,
                "truncated": truncated,
                "redacted": True,
                "model_invocations": 0,
                **current_context(),
            }
        },
    )

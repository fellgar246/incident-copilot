"""Demo services, log groups, and metrics a read-only tool may touch."""

from __future__ import annotations

from enum import StrEnum

from incident_contracts.surface import DEMO_SERVICES

from cloudwatch_tool.errors import AllowlistError

DEFAULT_PROJECT = "ai-incident-copilot"
DEFAULT_ENVIRONMENT = "dev"
DEFAULT_METRIC_NAMESPACE = "AIIncidentCopilot/Demo"

LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARN", "ERROR")


class MetricName(StrEnum):
    """Metrics the agent may request. Fixture signals map onto these names."""

    ERROR_RATE = "error_rate"
    REQUEST_COUNT = "request_count"
    LATENCY_P95 = "latency_p95"
    THROTTLES = "throttles"
    DURATION = "duration"
    CUSTOM_HEALTH = "custom_health"


DECLARED_METRICS: tuple[MetricName, ...] = tuple(MetricName)

_FIXTURE_SIGNALS: dict[str, MetricName] = {
    "5xx_rate": MetricName.ERROR_RATE,
    "latency_p95": MetricName.LATENCY_P95,
    "cpu_percent": MetricName.CUSTOM_HEALTH,
    "db_connections": MetricName.CUSTOM_HEALTH,
    "ApproximateNumberOfMessagesVisible": MetricName.CUSTOM_HEALTH,
    "ApproximateAgeOfOldestMessage": MetricName.CUSTOM_HEALTH,
    "worker_duration_p95": MetricName.DURATION,
}

SIGNALS: dict[MetricName, tuple[str, ...]] = {
    MetricName.ERROR_RATE: ("error_rate", "5xx_rate"),
    MetricName.REQUEST_COUNT: ("request_count",),
    MetricName.LATENCY_P95: ("latency_p95",),
    MetricName.THROTTLES: ("throttles",),
    MetricName.DURATION: ("duration", "worker_duration_p95"),
    MetricName.CUSTOM_HEALTH: (
        "custom_health",
        "cpu_percent",
        "db_connections",
        "ApproximateNumberOfMessagesVisible",
        "ApproximateAgeOfOldestMessage",
    ),
}


def require_service(service: str) -> str:
    """Return `service` when it is one of the demo services."""
    if service not in DEMO_SERVICES:
        raise AllowlistError(f"service is not allowlisted: {service}")
    return service


def log_group_name(
    service: str,
    *,
    project: str = DEFAULT_PROJECT,
    environment: str = DEFAULT_ENVIRONMENT,
) -> str:
    """Return the only log group a tool may read for `service`."""
    require_service(service)
    return f"/{project}/{environment}/{service}"


def canonical_metric(name: str) -> MetricName | None:
    """Map a declared metric or a known fixture signal onto the allowlist."""
    try:
        return MetricName(name)
    except ValueError:
        return _FIXTURE_SIGNALS.get(name)


def require_metric(name: str) -> MetricName:
    """Return a declared metric. Fixture signal names are not accepted as input."""
    try:
        return MetricName(name)
    except ValueError as exc:
        raise AllowlistError(f"metric is not allowlisted: {name}") from exc

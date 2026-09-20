"""Scenario catalogs used by the deterministic simulator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from incident_contracts.enums import ScenarioId, Severity


@dataclass(frozen=True)
class ScenarioSpec:
    scenario: ScenarioId
    service: str
    severity: Severity
    alarm_name: str


SPECS: dict[ScenarioId, ScenarioSpec] = {
    ScenarioId.DEPLOYMENT_REGRESSION: ScenarioSpec(
        scenario=ScenarioId.DEPLOYMENT_REGRESSION,
        service="payments-api",
        severity=Severity.HIGH,
        alarm_name="payments-5xx-rate",
    ),
    ScenarioId.CONNECTION_POOL_EXHAUSTION: ScenarioSpec(
        scenario=ScenarioId.CONNECTION_POOL_EXHAUSTION,
        service="orders-api",
        severity=Severity.HIGH,
        alarm_name="orders-latency-p95",
    ),
    ScenarioId.QUEUE_BACKLOG: ScenarioSpec(
        scenario=ScenarioId.QUEUE_BACKLOG,
        service="notifications-worker",
        severity=Severity.MEDIUM,
        alarm_name="notifications-oldest-message-age",
    ),
    ScenarioId.FALSE_POSITIVE: ScenarioSpec(
        scenario=ScenarioId.FALSE_POSITIVE,
        service="payments-api",
        severity=Severity.LOW,
        alarm_name="payments-cpu-brief-spike",
    ),
}


def at(origin: datetime, minutes: int, seconds: int = 0) -> datetime:
    return origin + timedelta(minutes=minutes, seconds=seconds)

#!/usr/bin/env python3
"""Seed demo telemetry and print the evidence the read-only tools return.

The tool clock is the fixture start plus 10 minutes, so the relative windows
cover the seeded samples instead of wall-clock now.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import timedelta

from incident_contracts.enums import ScenarioId
from incident_contracts.models import Deployment, IncidentFixture

from simulator import emit_metric_points, emit_structured_logs, seed_fixture, simulate


class _IgnoreDeployments:
    def write_deployment(self, deployment: Deployment) -> None:
        del deployment


def publish_cloudwatch(fixture: IncidentFixture) -> None:
    """Write fixture logs and metrics into CloudWatch. Deployments stay in DynamoDB."""
    from cloudwatch_tool.cloudwatch import CloudWatchTelemetryStore

    store = CloudWatchTelemetryStore.from_env()
    seed_fixture(fixture, logs=store, metrics=store, deployments=_IgnoreDeployments())


def evidence_report(scenario: ScenarioId, seed: str) -> dict[str, object]:
    """Seed an in-memory store and return the tool payloads for `scenario`."""
    from cloudwatch_tool.allowlist import MetricName
    from cloudwatch_tool.limits import ToolLimits
    from cloudwatch_tool.store import InMemoryTelemetryStore
    from cloudwatch_tool.tools import query_logs, query_metrics
    from deployments_tool.limits import ToolLimits as DeploymentLimits
    from deployments_tool.store import MemoryDeploymentStore
    from deployments_tool.tools import get_recent_deployments

    fixture = simulate(scenario, seed=seed)
    logs = InMemoryTelemetryStore()
    deployments = MemoryDeploymentStore()
    seed_fixture(fixture, logs=logs, metrics=logs, deployments=deployments)
    moment = fixture.incident.started_at + timedelta(minutes=10)
    log_limits = ToolLimits()
    deployment_limits = DeploymentLimits()
    log_result = query_logs(
        {
            "service": fixture.incident.service,
            "start_minutes_ago": log_limits.max_log_window_minutes,
            "limit": log_limits.max_log_results,
        },
        store=logs,
        now=moment,
        limits=log_limits,
    )
    metrics = {
        metric.value: query_metrics(
            {
                "service": fixture.incident.service,
                "metric": metric.value,
                "start_minutes_ago": log_limits.max_metric_window_minutes,
            },
            store=logs,
            now=moment,
            limits=log_limits,
        ).model_dump(mode="json")
        for metric in MetricName
    }
    deployment_result = get_recent_deployments(
        {"service": fixture.incident.service, "lookback_hours": 24},
        store=deployments,
        now=moment,
        limits=deployment_limits,
    )
    return {
        "scenario": scenario.value,
        "seed": seed,
        "service": fixture.incident.service,
        "emitted_logs": [json.loads(line) for line in emit_structured_logs(fixture)],
        "emitted_metrics": emit_metric_points(fixture),
        "query_logs": log_result.model_dump(mode="json"),
        "query_metrics": metrics,
        "get_recent_deployments": deployment_result.model_dump(mode="json"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario",
        nargs="?",
        default=ScenarioId.DEPLOYMENT_REGRESSION.value,
        choices=[item.value for item in ScenarioId],
    )
    parser.add_argument("--seed", default="demo")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Seed every demo scenario instead of a single one.",
    )
    parser.add_argument(
        "--put-cloudwatch",
        action="store_true",
        help="Also write logs and metrics to CloudWatch in AWS_REGION.",
    )
    args = parser.parse_args(argv)
    scenarios = list(ScenarioId) if args.all else [ScenarioId(args.scenario)]
    for scenario in scenarios:
        fixture = simulate(scenario, seed=args.seed)
        if args.put_cloudwatch:
            publish_cloudwatch(fixture)
        report = evidence_report(scenario, args.seed)
        report["published_cloudwatch"] = bool(args.put_cloudwatch)
        sys.stdout.write(json.dumps(report) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

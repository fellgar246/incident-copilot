from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OBSERVABILITY = REPO_ROOT / "infra" / "modules" / "observability" / "main.tf"
OBSERVABILITY_VARIABLES = REPO_ROOT / "infra" / "modules" / "observability" / "variables.tf"
CLOUDWATCH = REPO_ROOT / "infra" / "modules" / "cloudwatch" / "main.tf"
DEV = REPO_ROOT / "infra" / "environments" / "dev" / "main.tf"


def test_log_groups_keep_seven_day_retention() -> None:
    source = OBSERVABILITY.read_text(encoding="utf-8")
    variables = OBSERVABILITY_VARIABLES.read_text(encoding="utf-8")
    assert source.count("retention_in_days = var.log_retention_days") == 2
    assert "default     = 7" in variables
    assert "cloudwatch:PutMetricData" in source
    assert "cloudwatch:namespace" in source
    assert "AIIncidentCopilot/Observability" in variables


def test_dashboard_includes_cost_and_queue_metrics() -> None:
    dashboard = CLOUDWATCH.read_text(encoding="utf-8")
    for name in (
        "incidents_total",
        "investigation_latency",
        "tool_error_rate",
        "queue_age",
        "dlq_messages",
        "estimated_cost",
        "EstimatedCostPerIncident",
        "TokensPerIncident",
        "ToolCallsPerIncident",
        "RuntimePerIncident",
        "RagCallsPerIncident",
    ):
        assert name in dashboard
    dev = DEV.read_text(encoding="utf-8")
    assert 'source = "../../modules/observability"' in dev
    assert 'source = "../../modules/cloudwatch"' in dev
    assert "log_retention_days = var.log_retention_days" in dev

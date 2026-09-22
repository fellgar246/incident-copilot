from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TELEMETRY = REPO_ROOT / "infra" / "modules" / "telemetry" / "main.tf"
TELEMETRY_VARIABLES = REPO_ROOT / "infra" / "modules" / "telemetry" / "variables.tf"
IAM = REPO_ROOT / "infra" / "modules" / "iam" / "main.tf"
DEV = REPO_ROOT / "infra" / "environments" / "dev" / "main.tf"


def test_cloudwatch_read_role_is_allowlisted() -> None:
    iam = IAM.read_text(encoding="utf-8")
    assert "cloudwatch-read-tool" in iam
    assert "lambda.amazonaws.com" in iam
    source = TELEMETRY.read_text(encoding="utf-8")
    policy = source[source.index('data "aws_iam_policy_document" "cloudwatch_read"') :]
    assert "logs:FilterLogEvents" in policy
    assert "logs:GetLogEvents" in policy
    assert "cloudwatch:GetMetricStatistics" in policy
    assert "cloudwatch:namespace" in policy
    assert "logs:PutLogEvents" not in policy
    assert "logs:StartQuery" not in policy
    assert "cloudwatch:PutMetricData" not in policy
    assert "AIIncidentCopilot/Demo" in TELEMETRY_VARIABLES.read_text(encoding="utf-8")
    services = TELEMETRY_VARIABLES.read_text(encoding="utf-8")
    for service in ("payments-api", "orders-api", "notifications-worker"):
        assert service in services
    assert 'source = "../../modules/telemetry"' in DEV.read_text(encoding="utf-8")
    assert "cloudwatch_read_tool_role_name" in DEV.read_text(encoding="utf-8")

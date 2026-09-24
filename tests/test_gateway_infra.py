from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IAM = REPO_ROOT / "infra" / "modules" / "iam" / "main.tf"
TELEMETRY = REPO_ROOT / "infra" / "modules" / "telemetry" / "main.tf"
DEV = REPO_ROOT / "infra" / "environments" / "dev" / "main.tf"
SCRIPT = REPO_ROOT / "scripts" / "register_gateway.py"
REGISTER = REPO_ROOT / "services" / "agent" / "src" / "agent" / "register.py"


def test_gateway_role_is_scoped_and_search_stays_off() -> None:
    iam = IAM.read_text(encoding="utf-8")
    assert "agentcore-gateway" in iam
    assert "dynamodb:GetItem" in iam
    gateway = iam[iam.index('resource "aws_iam_role" "agentcore_gateway"') :]
    assert "logs:*" not in gateway
    assert "s3:*" not in gateway
    assert "bedrock:InvokeModel" not in gateway
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    assert "gateway_cloudwatch_read" in telemetry
    assert "logs:StartQuery" not in telemetry
    assert "gateway_role_name" in DEV.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    register = REGISTER.read_text(encoding="utf-8")
    assert "GATEWAY_APPLY" in script
    assert "GATEWAY_SEARCH_ENABLED" in register
    assert "WEB_SEARCH_ENABLED" in register
    assert "refusing to enable" in register

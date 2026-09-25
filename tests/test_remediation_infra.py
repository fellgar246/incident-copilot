from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IAM = REPO_ROOT / "infra" / "modules" / "iam" / "main.tf"


def test_remediation_role_cannot_change_compute() -> None:
    text = IAM.read_text(encoding="utf-8")
    assert "remediation-tool" in text
    assert "dynamodb:UpdateItem" in text
    assert "ssm:SendCommand" in text
    assert "ec2:*" in text
    role = text[text.index('resource "aws_iam_role" "remediation_tool"') :]
    assert "Action: *" not in role
    assert "lambda:InvokeFunction" in role

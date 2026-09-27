from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(REPO_ROOT / "scripts" / script), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_estimate_cost_prints_observed_demo_session() -> None:
    summary = json.loads(
        (REPO_ROOT / "evals" / "expected" / "last_run.json").read_text(encoding="utf-8")
    )
    observed = f"{float(summary['cost_per_successful_diagnosis']):.8f}"
    result = _run("estimate_cost.py")
    assert result.returncode == 0, result.stderr
    assert "deployment_regression" in result.stdout
    assert f"observed_estimated_usd: {observed}" in result.stdout
    assert "target: <= 5.00" in result.stdout
    assert "not an AWS invoice" in result.stdout


def test_verify_quotas_stops_when_ai_is_disabled() -> None:
    result = _run("verify_quotas.py")
    assert result.returncode == 0, result.stderr
    assert "quotas ok" in result.stdout


def test_secret_scan_passes() -> None:
    result = _run("scan_secrets.py")
    assert result.returncode == 0, result.stderr


def test_smoke_dry_run_lists_the_release_calls() -> None:
    result = _run("smoke_deploy.py", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "GET /health" in result.stdout
    assert "POST /incidents/simulate" in result.stdout
    assert "expect 403" in result.stdout


def test_cleanup_refuses_production_and_dry_runs_dev() -> None:
    refused = _run("cleanup_dev.py", "--environment", "prod", "--apply", "--confirm", "destroy-dev")
    assert refused.returncode == 2
    assert "refusing" in refused.stderr
    dry = _run("cleanup_dev.py", "--environment", "dev")
    assert dry.returncode == 0, dry.stderr
    assert "dry-run" in dry.stdout
    unconfirmed = _run("cleanup_dev.py", "--environment", "ephemeral-ci", "--apply")
    assert unconfirmed.returncode == 2


def test_remote_backend_swap_is_local_to_the_working_copy(tmp_path: Path) -> None:
    source = (REPO_ROOT / "infra" / "environments" / "dev" / "versions.tf").read_text(
        encoding="utf-8"
    )
    versions = tmp_path / "versions.tf"
    versions.write_text(source, encoding="utf-8")
    hcl = tmp_path / "backend.hcl"
    result = _run(
        "configure_remote_backend.py",
        "--versions",
        str(versions),
        "--bucket",
        "example-tfstate",
        "--table",
        "example-locks",
        "--write-hcl",
        str(hcl),
    )
    assert result.returncode == 0, result.stderr
    rewritten = versions.read_text(encoding="utf-8")
    assert 'backend "s3"' in rewritten
    assert 'backend "local"' not in rewritten
    assert 'bucket         = "example-tfstate"' in hcl.read_text(encoding="utf-8")
    committed = (REPO_ROOT / "infra" / "environments" / "dev" / "versions.tf").read_text(
        encoding="utf-8"
    )
    assert 'backend "local"' in committed


def test_pipeline_uses_oidc_and_environment_protection() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    destroy = (REPO_ROOT / ".github" / "workflows" / "destroy-ephemeral.yml").read_text(
        encoding="utf-8"
    )
    for step in (
        "Lint",
        "Typecheck",
        "Unit tests",
        "Integration tests",
        "Security checks",
        "Offline AI evaluations",
        "Terraform fmt and validate",
        "Terraform plan",
        "Deploy dev",
        "Smoke test",
    ):
        assert step in workflow
    assert "environment: dev" in workflow
    assert "role-to-assume:" in workflow
    assert "aws-access-key-id" not in workflow
    assert "aws-secret-access-key" not in workflow
    assert "environment: dev" in destroy
    assert "destroy-dev" in destroy


def test_ci_role_trusts_the_dev_environment_only() -> None:
    assume = (REPO_ROOT / "infra" / "modules" / "iam" / "main.tf").read_text(encoding="utf-8")
    policy = (REPO_ROOT / "infra" / "modules" / "iam" / "ci_deploy.tf").read_text(encoding="utf-8")
    assert "environment:${var.github_environment}" in assume
    assert "job_workflow_ref" in assume
    assert "DenyLongLivedCredentials" in policy
    assert "ci-deploy-role" in assume
    assert "skeleton" not in assume.lower()
    dev = (REPO_ROOT / "infra" / "environments" / "dev" / "main.tf").read_text(encoding="utf-8")
    assert "module.frontend.dashboard_url" in dev


def test_destroy_is_not_blocked_by_prevent_destroy() -> None:
    for path in (REPO_ROOT / "infra").rglob("*.tf"):
        if ".terraform" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        assert "prevent_destroy" not in text
    corpus = (REPO_ROOT / "infra" / "modules" / "knowledge-base" / "main.tf").read_text(
        encoding="utf-8"
    )
    web = (REPO_ROOT / "infra" / "modules" / "frontend" / "main.tf").read_text(encoding="utf-8")
    assert "force_destroy = true" in corpus
    assert "force_destroy = true" in web


def test_release_docs_cover_cost_security_and_tradeoffs() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for phrase in (
        "DynamoDB vs RDS",
        "Managed Knowledge Base vs OpenSearch",
        "Lambda vs ECS",
        "Single agent vs multi-agent",
        "No NAT Gateway",
        "USD 0.00046039",
        "ci-deploy-role",
    ):
        assert phrase in readme
    assert (REPO_ROOT / "docs" / "architecture" / "security-model.md").is_file()
    assert (REPO_ROOT / "docs" / "architecture" / "diagram.md").is_file()
    assert (REPO_ROOT / "docs" / "runbooks" / "cost-explorer-review.md").is_file()
    assert (REPO_ROOT / "docs" / "architecture" / "release-risks.md").is_file()
    assert (REPO_ROOT / "docs" / "backlog.md").is_file()
    assert (REPO_ROOT / "docs" / "adrs" / "ADR-010-platform-cicd.md").is_file()

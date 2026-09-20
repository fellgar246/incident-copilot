from __future__ import annotations

import re
import subprocess
from pathlib import Path

from observability.correlation import new_correlation_id

REPO_ROOT = Path(__file__).resolve().parents[1]

TERRAFORM_REQUIRED_VARIABLES = (
    "monthly_budget_usd",
    "log_retention_days",
    "max_incidents_per_day",
    "knowledge_corpus_enabled",
    "ai_enabled",
)

DEFAULT_TAGS = (
    "project     = var.project",
    "environment = var.environment",
    "owner       = var.owner",
)

AWS_ACCESS_KEY_PATTERN = re.compile(r"AKIA[0-9A-Z]{16}")
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(aws_secret_access_key|aws_access_key_id)\s*=\s*['\"]?[A-Za-z0-9/+=]{8,}",
    re.IGNORECASE,
)

SCAN_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".tf",
    ".yml",
    ".yaml",
    ".md",
    ".env",
    ".toml",
    ".json",
}


def _tracked_files() -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        text=True,
    )
    return [path for path in output.split("\0") if path]


def _is_gitignored(relative: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", relative],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


def test_new_correlation_id_is_unique() -> None:
    left = new_correlation_id()
    right = new_correlation_id()
    assert left != right
    assert len(left) == 36


def test_gitignore_excludes_env_and_state() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".env", "*.tfstate", "credentials", "node_modules/", "backend.hcl"):
        assert pattern in gitignore
    assert "!.env.example" in gitignore
    assert "!*.tfvars.example" in gitignore
    assert "!backend.hcl.example" in gitignore


def test_env_example_is_versionable_and_real_secrets_are_not() -> None:
    examples = (
        ".env.example",
        "infra/environments/dev/terraform.tfvars.example",
        "infra/environments/dev/backend.hcl.example",
    )
    for relative in examples:
        assert (REPO_ROOT / relative).is_file()
        assert not _is_gitignored(relative)

    tracked = set(_tracked_files())
    assert ".env" not in tracked
    for path in tracked:
        name = Path(path).name
        assert not path.endswith(".tfstate")
        assert name != ".env"
        assert not (path.endswith(".tfvars") and not path.endswith(".tfvars.example"))
        assert name != "backend.hcl"


def test_tracked_files_do_not_embed_aws_credentials() -> None:
    for relative in _tracked_files():
        suffix = Path(relative).suffix
        if suffix not in SCAN_SUFFIXES and Path(relative).name != ".env.example":
            continue
        text = (REPO_ROOT / relative).read_text(encoding="utf-8", errors="ignore")
        assert AWS_ACCESS_KEY_PATTERN.search(text) is None, relative
        assert SECRET_ASSIGNMENT_PATTERN.search(text) is None, relative


def test_terraform_bootstrap_exposes_required_variables() -> None:
    variables = (REPO_ROOT / "infra/environments/dev/variables.tf").read_text(encoding="utf-8")
    for name in TERRAFORM_REQUIRED_VARIABLES:
        assert f'variable "{name}"' in variables
    versions = (REPO_ROOT / "infra/environments/dev/versions.tf").read_text(encoding="utf-8")
    for tag_line in DEFAULT_TAGS:
        assert tag_line in versions
    assert "region = var.aws_region" in versions
    assert 'default     = "us-east-1"' in variables

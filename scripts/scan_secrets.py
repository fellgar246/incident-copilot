"""Fail when tracked files contain AWS access keys or static credential assignments."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AWS_ACCESS_KEY_PATTERN = re.compile(r"AKIA[0-9A-Z]{16}")
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(aws_secret_access_key|aws_access_key_id)\s*=\s*['\"]?[A-Za-z0-9/+=]{8,}",
    re.IGNORECASE,
)
STATIC_ACTION_INPUT = re.compile(r"aws-(?:access-key-id|secret-access-key)\s*:")
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


def tracked_files() -> list[str]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=REPO_ROOT, text=True)
    return [path for path in output.split("\0") if path]


def findings_in(relative: str, text: str) -> list[str]:
    found: list[str] = []
    if AWS_ACCESS_KEY_PATTERN.search(text):
        found.append(f"{relative}: embedded access key id")
    if SECRET_ASSIGNMENT_PATTERN.search(text):
        found.append(f"{relative}: static credential assignment")
    if relative.startswith(".github/workflows/") and STATIC_ACTION_INPUT.search(text):
        found.append(f"{relative}: static AWS credential input")
    return found


def main() -> int:
    problems: list[str] = []
    for relative in tracked_files():
        path = REPO_ROOT / relative
        if not path.is_file():
            continue
        suffix = path.suffix
        if suffix not in SCAN_SUFFIXES and path.name != ".env.example":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        problems.extend(findings_in(relative, text))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("secret scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

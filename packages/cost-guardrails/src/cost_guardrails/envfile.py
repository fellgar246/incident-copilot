"""Minimal .env file parser used by tests and local bootstrap."""

from __future__ import annotations

from pathlib import Path


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines, ignoring blanks and comments."""
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid env line in {path}: {raw_line!r}")
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values

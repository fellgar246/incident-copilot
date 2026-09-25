"""Load the versioned evaluation dataset."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

PROFILES: tuple[str, ...] = ("pr", "release", "full")
_PROFILE_RANK = {name: index for index, name in enumerate(PROFILES)}


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    cohort: str
    incident_fixture: str
    expected_primary_cause: str
    required_evidence: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    acceptable_remediations: list[str] = Field(default_factory=list)
    profile: str
    check: str
    expected_source: str = ""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def dataset_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "evals" / "incidents.jsonl"


def gates_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "evals" / "expected" / "gates.json"


def summary_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "evals" / "expected" / "last_run.json"


def load_cases(root: Path | None = None, *, profile: str = "full") -> list[EvalCase]:
    """Return cases included in `profile`. `release` includes `pr`; `full` includes both."""
    if profile not in _PROFILE_RANK:
        raise ValueError(f"unknown profile: {profile}")
    limit = _PROFILE_RANK[profile]
    cases: list[EvalCase] = []
    for line in dataset_path(root).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = EvalCase.model_validate_json(line)
        if _PROFILE_RANK[item.profile] <= limit:
            cases.append(item)
    return cases


def load_gates(root: Path | None = None) -> dict[str, object]:
    payload = json.loads(gates_path(root).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("gates file must be an object")
    return payload

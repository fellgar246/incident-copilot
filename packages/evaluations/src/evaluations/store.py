"""Read and write the latest evaluation summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluations.dataset import summary_path


def write_summary(summary: dict[str, Any], root: Path | None = None) -> Path:
    path = summary_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return path


def load_summary(root: Path | None = None) -> dict[str, Any]:
    path = summary_path(root)
    if not path.is_file():
        return {
            "profile": "none",
            "case_count": 0,
            "evaluation_pass_rate": 0.0,
            "diagnosis_accuracy": 0.0,
            "groundedness": 0.0,
            "unsafe_action_count": 0,
            "avg_tool_calls": 0.0,
            "avg_estimated_cost": 0.0,
            "passed": False,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("evaluation summary must be an object")
    return payload

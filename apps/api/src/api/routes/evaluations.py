"""GET /evaluations. Returns the latest offline run summary."""

from __future__ import annotations

from typing import Any

from evaluations.store import load_summary
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["evaluations"])


class EvaluationSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    profile: str
    case_count: int
    evaluation_pass_rate: float
    diagnosis_accuracy: float
    groundedness: float
    unsafe_action_count: int
    avg_tool_calls: float
    avg_estimated_cost: float
    passed: bool = False


@router.get("/evaluations", response_model=EvaluationSummary)
def get_evaluations() -> dict[str, Any]:
    return load_summary()

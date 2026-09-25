"""Sample a fraction of finished investigations. Cost stops skip scoring."""

from __future__ import annotations

import hashlib

from incident_contracts.models import Diagnosis
from observability.metrics import record_metric


def should_sample(incident_id: str, rate: float) -> bool:
    """Stable sample. The same incident id always lands on the same side of `rate`."""
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    bucket = int(hashlib.sha256(incident_id.encode()).hexdigest()[:8], 16) % 10_000
    return bucket < int(rate * 10_000)


def record_sampled_evaluation(
    *,
    incident_id: str,
    rate: float,
    diagnosis: Diagnosis | None,
    cost_stopped: bool,
) -> None:
    """Record one structural score. A cost stop disables evaluation before any other work."""
    if cost_stopped or diagnosis is None or not should_sample(incident_id, rate):
        return
    record_metric("evaluation_score", _structural_score(diagnosis), unit="None")


def _structural_score(diagnosis: Diagnosis) -> float:
    action = diagnosis.recommended_action.lower()
    if diagnosis.destructive or "delete_resource" in action:
        return 0.0
    if diagnosis.confidence >= 0.7 and not diagnosis.evidence:
        return 0.0
    return 1.0

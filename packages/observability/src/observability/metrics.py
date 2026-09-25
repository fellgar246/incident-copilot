"""In-process counters emitted as CloudWatch Embedded Metric Format."""

from __future__ import annotations

import json
import logging
import time
from threading import Lock
from typing import Any

LOGGER = logging.getLogger("observability.metrics")
METRIC_NAMESPACE = "AIIncidentCopilot/Observability"

SYSTEM_METRICS: tuple[str, ...] = (
    "incidents_total",
    "incidents_by_status",
    "investigation_latency",
    "tool_error_rate",
    "queue_age",
    "dlq_messages",
)

AI_METRICS: tuple[str, ...] = (
    "llm_calls",
    "input_tokens",
    "output_tokens",
    "agent_turns",
    "tool_calls",
    "rag_calls",
    "confidence",
    "evaluation_score",
    "estimated_cost",
)

_LOCK = Lock()
_COUNTERS: dict[str, float] = {}
_TOOL_CALLS = 0
_TOOL_ERRORS = 0


def record_metric(
    name: str,
    value: float,
    *,
    unit: str = "Count",
    dimensions: dict[str, str] | None = None,
) -> None:
    """Add to the in-process total and emit one EMF line for CloudWatch."""
    if name not in SYSTEM_METRICS and name not in AI_METRICS:
        raise ValueError(f"unknown metric: {name}")
    with _LOCK:
        _COUNTERS[name] = _COUNTERS.get(name, 0.0) + value
    _emit(name, value, unit=unit, dimensions=dimensions or {})


def record_tool_result(*, ok: bool) -> None:
    """Track tool success so tool_error_rate can be read back."""
    global _TOOL_CALLS, _TOOL_ERRORS
    with _LOCK:
        _TOOL_CALLS += 1
        if not ok:
            _TOOL_ERRORS += 1
    _emit("tool_error_rate", 0.0 if ok else 1.0, unit="None", dimensions={})


def snapshot() -> dict[str, float]:
    """Return accumulated metric totals for the current process."""
    with _LOCK:
        totals = dict(_COUNTERS)
        calls = _TOOL_CALLS
        errors = _TOOL_ERRORS
    if calls:
        totals["tool_error_rate"] = errors / calls
    return totals


def reset_metrics() -> None:
    """Clear counters. Tests use this between cases."""
    global _TOOL_CALLS, _TOOL_ERRORS
    with _LOCK:
        _COUNTERS.clear()
        _TOOL_CALLS = 0
        _TOOL_ERRORS = 0


def _emit(name: str, value: float, *, unit: str, dimensions: dict[str, str]) -> None:
    dimension_keys = sorted(dimensions)
    body: dict[str, Any] = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": METRIC_NAMESPACE,
                    "Dimensions": [dimension_keys] if dimension_keys else [[]],
                    "Metrics": [{"Name": name, "Unit": unit}],
                }
            ],
        },
        name: value,
    }
    body.update(dimensions)
    LOGGER.info(json.dumps(body))

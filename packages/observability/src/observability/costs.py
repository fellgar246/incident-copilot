"""Roll agent-run counters into the per-incident cost series."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

PER_INCIDENT_SERIES: tuple[str, ...] = (
    "EstimatedCostPerIncident",
    "TokensPerIncident",
    "ToolCallsPerIncident",
    "RuntimePerIncident",
    "RagCallsPerIncident",
)


class RunCounters(Protocol):
    incident_id: str
    model_calls: int
    input_tokens: int
    output_tokens: int
    tool_calls: int
    rag_calls: int
    runtime_ms: int
    estimated_cost_usd: float


class IncidentCounters(Protocol):
    incident_id: str
    status: Any
    confidence: float | None


def summarize_incident(
    incident_id: str, runs: Sequence[RunCounters]
) -> dict[str, float | int | str]:
    """Sum one incident's runs into the stable cost series."""
    owned = [run for run in runs if run.incident_id == incident_id]
    return {
        "incident_id": incident_id,
        "EstimatedCostPerIncident": round(sum(run.estimated_cost_usd for run in owned), 8),
        "TokensPerIncident": sum(run.input_tokens + run.output_tokens for run in owned),
        "ToolCallsPerIncident": sum(run.tool_calls for run in owned),
        "RuntimePerIncident": sum(run.runtime_ms for run in owned),
        "RagCallsPerIncident": sum(run.rag_calls for run in owned),
    }


def cost_series(
    incidents: Sequence[IncidentCounters],
    runs: Sequence[RunCounters],
    *,
    queue_age: float = 0.0,
    dlq_messages: float = 0.0,
    evaluation_score: float | None = None,
    tool_error_rate: float = 0.0,
) -> dict[str, object]:
    """Build the system and AI series returned by GET /metrics/costs."""
    by_status: dict[str, int] = {}
    confidences: list[float] = []
    for incident in incidents:
        status = getattr(incident.status, "value", str(incident.status))
        by_status[status] = by_status.get(status, 0) + 1
        if incident.confidence is not None:
            confidences.append(incident.confidence)
    latency_values = [run.runtime_ms for run in runs]
    latency = sum(latency_values) / len(latency_values) if latency_values else 0.0
    return {
        "incidents_total": len(incidents),
        "incidents_by_status": by_status,
        "investigation_latency": round(latency, 3),
        "tool_error_rate": tool_error_rate,
        "queue_age": queue_age,
        "dlq_messages": dlq_messages,
        "llm_calls": sum(run.model_calls for run in runs),
        "input_tokens": sum(run.input_tokens for run in runs),
        "output_tokens": sum(run.output_tokens for run in runs),
        "agent_turns": sum(run.model_calls for run in runs),
        "tool_calls": sum(run.tool_calls for run in runs),
        "rag_calls": sum(run.rag_calls for run in runs),
        "confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "evaluation_score": evaluation_score,
        "estimated_cost": round(sum(run.estimated_cost_usd for run in runs), 8),
    }

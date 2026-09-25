"""GET /metrics/costs. Summaries come from stored incidents and agent runs."""

from __future__ import annotations

from fastapi import APIRouter, Request
from observability.costs import cost_series, summarize_incident
from observability.metrics import snapshot
from pydantic import BaseModel, ConfigDict

from api.deps import get_container

router = APIRouter(tags=["metrics"])


class IncidentCostSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    EstimatedCostPerIncident: float
    TokensPerIncident: int
    ToolCallsPerIncident: int
    RuntimePerIncident: int
    RagCallsPerIncident: int


class CostSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incidents_total: int
    incidents_by_status: dict[str, int]
    investigation_latency: float
    tool_error_rate: float
    queue_age: float
    dlq_messages: float
    llm_calls: int
    input_tokens: int
    output_tokens: int
    agent_turns: int
    tool_calls: int
    rag_calls: int
    confidence: float | None
    evaluation_score: float | None
    estimated_cost: float


class CostMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    log_retention_days: int
    series: CostSeries
    incidents: list[IncidentCostSummary]


def build_cost_metrics(request: Request) -> CostMetricsResponse:
    container = get_container(request)
    incidents = container.service.list_incidents()
    runs = [
        run
        for incident in incidents
        for run in container.runs.list_for_incident(incident.incident_id)
    ]
    totals = snapshot()
    series = cost_series(
        incidents,
        runs,
        queue_age=float(totals.get("queue_age", 0.0)),
        dlq_messages=float(totals.get("dlq_messages", 0.0)),
        evaluation_score=totals.get("evaluation_score"),
        tool_error_rate=float(totals.get("tool_error_rate", 0.0)),
    )
    summaries = [
        IncidentCostSummary.model_validate(summarize_incident(item.incident_id, runs))
        for item in incidents
    ]
    return CostMetricsResponse(
        log_retention_days=container.settings.log_retention_days,
        series=CostSeries.model_validate(series),
        incidents=summaries,
    )


@router.get("/metrics/costs", response_model=CostMetricsResponse)
def metrics_costs(request: Request) -> CostMetricsResponse:
    return build_cost_metrics(request)

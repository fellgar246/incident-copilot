"""POST /incidents/{id}/investigate and GET /incidents/{id}/agent-runs."""

from __future__ import annotations

from typing import Annotated

from agent.investigate import InvestigationRejected, investigate
from agent.runs import AgentRunRecord
from cloudwatch_tool.tools import CloudWatchTools
from deployments_tool.tools import DeploymentTools
from fastapi import APIRouter, Header, HTTPException, Request, Response
from incident_contracts.errors import IncidentNotFoundError
from incident_contracts.surface import IDEMPOTENCY_HEADER
from observability.costs import summarize_incident
from observability.logging import bind_context
from observability.tracing import reconstruct_trace
from pydantic import BaseModel, ConfigDict

from api.deps import get_container, new_model

router = APIRouter(tags=["incidents"])


class AgentRunsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[AgentRunRecord]
    trace: dict[str, object]
    EstimatedCostPerIncident: float
    TokensPerIncident: int
    ToolCallsPerIncident: int
    RuntimePerIncident: int
    RagCallsPerIncident: int


@router.post(
    "/incidents/{id}/investigate",
    response_model=AgentRunRecord,
    responses={
        200: {"description": "Existing run for this Idempotency-Key."},
        400: {"description": "Idempotency-Key is required."},
        404: {"description": "incident not found"},
        409: {"description": "Invocation disabled or status does not allow investigation."},
        429: {"description": "Agent run quota reached. The incident is unchanged."},
    },
)
def investigate_incident(
    id: str,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
) -> AgentRunRecord:
    container = get_container(request)
    bind_context(incident_id=id)
    try:
        container.service.get(id)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc
    tools = CloudWatchTools(container.telemetry)
    replay = container.runs.get_by_idempotency(id, idempotency_key or "")
    try:
        record = investigate(
            incident_id=id,
            correlation_id=request.headers.get("x-correlation-id", ""),
            idempotency_key=idempotency_key or "",
            service=container.service,
            runs=container.runs,
            quotas=container.quotas,
            model=new_model(container),
            logs=tools,
            metrics=tools,
            deployments=DeploymentTools(container.deployments),
        )
    except InvestigationRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if replay is None:
        response.status_code = 201
    return record


@router.get(
    "/incidents/{id}/agent-runs",
    response_model=AgentRunsResponse,
    responses={404: {"description": "incident not found"}},
)
def list_agent_runs(id: str, request: Request) -> AgentRunsResponse:
    container = get_container(request)
    bind_context(incident_id=id)
    try:
        container.service.get(id)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc
    runs = container.runs.list_for_incident(id)
    summary = summarize_incident(id, runs)
    return AgentRunsResponse(
        runs=runs,
        trace=reconstruct_trace(id),
        EstimatedCostPerIncident=float(summary["EstimatedCostPerIncident"]),
        TokensPerIncident=int(summary["TokensPerIncident"]),
        ToolCallsPerIncident=int(summary["ToolCallsPerIncident"]),
        RuntimePerIncident=int(summary["RuntimePerIncident"]),
        RagCallsPerIncident=int(summary["RagCallsPerIncident"]),
    )

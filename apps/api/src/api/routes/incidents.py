"""Read-oriented incident API and deterministic simulate."""

from __future__ import annotations

import logging
from typing import Annotated

from cost_guardrails.exceptions import QuotaExceededError
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from incident_contracts.api_models import SimulateIncidentRequest
from incident_contracts.enums import IncidentStatus
from incident_contracts.errors import IncidentNotFoundError
from incident_contracts.events import detected_event_from_fixture
from incident_contracts.models import Incident, IncidentEvent
from incident_contracts.surface import IDEMPOTENCY_HEADER
from observability.logging import bind_context
from observability.metrics import record_metric
from observability.tracing import SPAN_INCIDENT_RECEIVED, start_span

from api.deps import AppContainer, get_container
from simulator import simulate

logger = logging.getLogger("api.incidents")

router = APIRouter(tags=["incidents"])

_IDEMPOTENCY_HEADER = IDEMPOTENCY_HEADER


@router.get("/incidents", response_model=list[Incident])
def list_incidents(
    request: Request,
    status: Annotated[IncidentStatus | None, Query()] = None,
    service: Annotated[str | None, Query(min_length=1)] = None,
) -> list[Incident]:
    return get_container(request).service.list_incidents(status=status, service=service)


@router.post(
    "/incidents/simulate",
    response_model=Incident,
    status_code=201,
    responses={
        200: {
            "model": Incident,
            "description": (
                "Existing incident for the same Idempotency-Key or simulation_id. "
                "Replays return 200 and never create a second incident."
            ),
        },
        429: {"description": "Daily incident quota reached."},
    },
)
def simulate_incident(
    payload: SimulateIncidentRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias=_IDEMPOTENCY_HEADER)] = None,
) -> Incident:
    container = get_container(request)
    fixture = simulate(payload.scenario, seed=payload.seed)
    if payload.simulation_id:
        fixture.incident.simulation_id = payload.simulation_id

    lookup_key = idempotency_key or fixture.incident.simulation_id
    existing = None
    if idempotency_key:
        existing = container.store.get_by_idempotency_key(idempotency_key)
    if existing is None and fixture.incident.simulation_id:
        existing = container.store.get_by_simulation_id(fixture.incident.simulation_id)
    if existing is None and fixture.incident.source_event_id:
        existing = container.store.get_by_source_event_id(fixture.incident.source_event_id)
    if existing is not None:
        bind_context(incident_id=existing.incident_id, correlation_id=existing.correlation_id)
        logger.info(
            "incident.simulate_replay",
            extra={
                "fields": {
                    "incident_id": existing.incident_id,
                    "idempotency_key_present": bool(lookup_key),
                }
            },
        )
        response.status_code = 200
        return existing

    _enforce_daily_quota(container)
    incident = container.service.ingest_fixture(fixture)
    container.deployments.save_many(fixture.deployments)
    for sample in fixture.telemetry.logs:
        container.telemetry.write_log(sample)
    for point in fixture.telemetry.metrics:
        container.telemetry.write_metric(point)
    if idempotency_key:
        container.store.remember_idempotency(idempotency_key, incident.incident_id)
    try:
        container.publisher.publish_detected(detected_event_from_fixture(fixture))
    except Exception:
        logger.exception(
            "incident.bus_publish_failed",
            extra={"fields": {"incident_id": incident.incident_id}},
        )
    bind_context(incident_id=incident.incident_id, correlation_id=incident.correlation_id)
    with start_span(SPAN_INCIDENT_RECEIVED):
        record_metric("incidents_total", 1)
        record_metric(
            "incidents_by_status",
            1,
            dimensions={"Status": incident.status.value},
        )
    logger.info(
        "incident.simulate_created",
        extra={"fields": {"incident_id": incident.incident_id, "scenario": payload.scenario.value}},
    )
    response.status_code = 201
    return incident


@router.get(
    "/incidents/{id}",
    response_model=Incident,
    responses={404: {"description": "incident not found"}},
)
def get_incident(id: str, request: Request) -> Incident:
    bind_context(incident_id=id)
    try:
        return get_container(request).service.get(id)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc


@router.get(
    "/incidents/{id}/events",
    response_model=list[IncidentEvent],
    responses={404: {"description": "incident not found"}},
)
def list_incident_events(id: str, request: Request) -> list[IncidentEvent]:
    bind_context(incident_id=id)
    container = get_container(request)
    try:
        container.service.get(id)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc
    return container.service.events(id)


def _enforce_daily_quota(container: AppContainer) -> None:
    used = len(container.service.list_incidents())
    try:
        container.quotas.enforce(
            "MAX_INCIDENTS_PER_DAY",
            used=used,
            limit=container.quotas.max_incidents_per_day,
        )
    except QuotaExceededError as exc:
        logger.warning(
            "incident.quota_exceeded",
            extra={"fields": {"quota_name": exc.quota_name, "stop_reason": exc.stop_reason}},
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": str(exc),
                "stop_reason": exc.stop_reason,
                "quota_name": exc.quota_name,
            },
        ) from exc

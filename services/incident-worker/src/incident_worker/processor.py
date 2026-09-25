"""Create or reuse an incident from a validated incident.detected.v1 event."""

from __future__ import annotations

import logging

from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import AppQuotas
from incident_contracts.events import IncidentDetectedV1, incident_from_detected
from incident_contracts.models import Incident
from incident_contracts.repository import IncidentRepository
from incident_contracts.service import IncidentService
from observability.logging import bind_context
from observability.metrics import record_metric
from observability.tracing import SPAN_INCIDENT_RECEIVED, start_span
from opentelemetry.trace import Span

logger = logging.getLogger("incident_worker")


def ingest_detected(
    event: IncidentDetectedV1,
    *,
    repository: IncidentRepository,
    quotas: AppQuotas | None = None,
) -> Incident:
    """Idempotent ingest. Duplicate event_id values return the existing incident."""
    bind_context(event_id=event.event_id, correlation_id=event.correlation_id)
    with start_span(SPAN_INCIDENT_RECEIVED, correlation_id=event.correlation_id) as span:
        return _ingest(event, repository=repository, quotas=quotas, span=span)


def _ingest(
    event: IncidentDetectedV1,
    *,
    repository: IncidentRepository,
    quotas: AppQuotas | None,
    span: Span,
) -> Incident:
    existing = _existing_incident(repository, event)
    if existing is not None:
        bind_context(incident_id=existing.incident_id, correlation_id=existing.correlation_id)
        span.set_attribute("incident_id", existing.incident_id)
        logger.info(
            "incident.ingest_replay",
            extra={
                "fields": {
                    "event_id": event.event_id,
                    "incident_id": existing.incident_id,
                    "correlation_id": existing.correlation_id,
                }
            },
        )
        return existing

    if quotas is not None:
        _enforce_daily_quota(repository, quotas)

    incident, alarm = incident_from_detected(event)
    created = IncidentService(repository).ingest(incident, alarm)
    bind_context(incident_id=created.incident_id, correlation_id=created.correlation_id)
    span.set_attribute("incident_id", created.incident_id)
    record_metric("incidents_total", 1)
    record_metric(
        "incidents_by_status",
        1,
        dimensions={"Status": created.status.value},
    )
    logger.info(
        "incident.ingest_created",
        extra={
            "fields": {
                "event_id": event.event_id,
                "incident_id": created.incident_id,
                "correlation_id": created.correlation_id,
                "scenario": event.scenario.value,
            }
        },
    )
    return created


def _existing_incident(
    repository: IncidentRepository, event: IncidentDetectedV1
) -> Incident | None:
    found = repository.get_by_source_event_id(event.event_id)
    if found is not None:
        return found
    found = repository.get_by_event_id(event.event_id)
    if found is not None:
        return found
    if event.simulation_id:
        return repository.get_by_simulation_id(event.simulation_id)
    return None


def _enforce_daily_quota(repository: IncidentRepository, quotas: AppQuotas) -> None:
    used = len(repository.list_incidents())
    try:
        quotas.enforce(
            "MAX_INCIDENTS_PER_DAY",
            used=used,
            limit=quotas.max_incidents_per_day,
        )
    except QuotaExceededError:
        logger.warning("incident.quota_exceeded")
        raise

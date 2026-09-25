"""Approve, reject, or execute a remediation that was proposed earlier."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response
from incident_contracts.actors import validate_actor
from incident_contracts.api_models import (
    ApproveIncidentRequest,
    RejectIncidentRequest,
    RemediateIncidentRequest,
)
from incident_contracts.enums import IncidentStatus
from incident_contracts.errors import (
    DomainError,
    DuplicateRemediationError,
    IllegalTransitionError,
    IncidentNotFoundError,
    InvalidActorError,
    InvalidApprovalError,
    RemediationDeniedError,
)
from incident_contracts.models import Incident
from incident_contracts.surface import IDEMPOTENCY_HEADER
from observability.logging import bind_context
from remediation_tool.runtime import RemediationTimeoutError
from remediation_tool.tools import RemediationTools

from api.deps import get_container

logger = logging.getLogger("api.remediation")

router = APIRouter(tags=["remediation"])


@router.post(
    "/incidents/{id}/approve",
    response_model=Incident,
    responses={
        400: {"description": "Idempotency-Key is required."},
        403: {"description": "Approval is missing, mismatched, or expired. Decision is DENIED."},
        404: {"description": "incident not found"},
        409: {"description": "Incident is not awaiting approval."},
    },
)
def approve_incident(
    id: str,
    payload: ApproveIncidentRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
    actor: Annotated[str | None, Header(alias="X-Actor")] = None,
) -> Incident:
    return _decide(
        id,
        request,
        response,
        idempotency_key=idempotency_key,
        actor=actor,
        kind="approve",
        approval_id=payload.approval_id,
    )


@router.post(
    "/incidents/{id}/reject",
    response_model=Incident,
    responses={
        400: {"description": "Idempotency-Key is required."},
        404: {"description": "incident not found"},
        409: {"description": "Incident is not awaiting approval."},
    },
)
def reject_incident(
    id: str,
    payload: RejectIncidentRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
    actor: Annotated[str | None, Header(alias="X-Actor")] = None,
) -> Incident:
    return _decide(
        id,
        request,
        response,
        idempotency_key=idempotency_key,
        actor=actor,
        kind="reject",
        approval_id=payload.approval_id,
    )


@router.post(
    "/incidents/{id}/remediate",
    response_model=Incident,
    responses={
        400: {"description": "Idempotency-Key is required."},
        403: {
            "description": (
                "Remediation without a valid, unexpired approval is DENIED. "
                "Also returned when REMEDIATION_ENABLED=false or the action is not allowlisted."
            ),
        },
        404: {"description": "incident not found"},
        409: {"description": "A remediation is already active, or the incident is not approved."},
        504: {"description": "The safe write exceeded its timeout and the incident is FAILED."},
    },
)
def remediate_incident(
    id: str,
    payload: RemediateIncidentRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
    actor: Annotated[str | None, Header(alias="X-Actor")] = None,
) -> Incident:
    _require_key(idempotency_key)
    assert idempotency_key is not None
    container = get_container(request)
    bind_context(incident_id=id)
    human = _actor(actor)
    replay_key = f"remediate:{id}:{idempotency_key}"
    existing = container.store.get_by_idempotency_key(replay_key)
    if existing is not None:
        response.status_code = 200
        return existing
    tools = RemediationTools(container.service)
    try:
        incident = tools.execute_remediation(
            id,
            approval_id=payload.approval_id,
            idempotency_key=idempotency_key,
            actor=human,
        )
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc
    except RemediationDeniedError as exc:
        raise HTTPException(
            status_code=403, detail={"decision": "DENIED", "error": str(exc)}
        ) from exc
    except DuplicateRemediationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (IllegalTransitionError, InvalidApprovalError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RemediationTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    container.store.remember_idempotency(replay_key, incident.incident_id)
    logger.info(
        "remediation.api_executed",
        extra={
            "fields": {
                "incident_id": id,
                "actor": human,
                "status": incident.status.value,
                "at": datetime.now(UTC).isoformat(),
            }
        },
    )
    response.status_code = 200
    return incident


def _decide(
    incident_id: str,
    request: Request,
    response: Response,
    *,
    idempotency_key: str | None,
    actor: str | None,
    kind: str,
    approval_id: str,
) -> Incident:
    _require_key(idempotency_key)
    assert idempotency_key is not None
    container = get_container(request)
    bind_context(incident_id=incident_id)
    human = _actor(actor)
    replay_key = f"{kind}:{incident_id}:{idempotency_key}"
    existing = container.store.get_by_idempotency_key(replay_key)
    if existing is not None:
        response.status_code = 200
        return existing
    moment = datetime.now(UTC)
    event_id = f"evt_{kind}_{incident_id}_{idempotency_key}"[:80]
    try:
        incident = container.service.get(incident_id)
        if kind == "approve":
            if incident.approval is None or incident.status is not IncidentStatus.AWAITING_APPROVAL:
                raise RemediationDeniedError("valid approval_id is required")
            updated = container.service.approve(
                incident_id,
                actor=human,
                at=moment,
                event_id=event_id,
                approval_id=approval_id,
                expires_at=incident.approval.expires_at,
            )
        else:
            updated = container.service.reject(
                incident_id,
                actor=human,
                at=moment,
                event_id=event_id,
                approval_id=approval_id,
            )
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc
    except (RemediationDeniedError, InvalidApprovalError) as exc:
        raise HTTPException(
            status_code=403, detail={"decision": "DENIED", "error": str(exc)}
        ) from exc
    except (IllegalTransitionError, DomainError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    container.store.remember_idempotency(replay_key, updated.incident_id)
    logger.info(
        "remediation.decided",
        extra={
            "fields": {
                "incident_id": incident_id,
                "actor": human,
                "approval_id": approval_id,
                "decision": kind,
            }
        },
    )
    response.status_code = 200
    return updated


def _require_key(idempotency_key: str | None) -> None:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")


def _actor(actor: str | None) -> str:
    chosen = actor or "human:demo"
    try:
        return validate_actor(chosen)
    except InvalidActorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

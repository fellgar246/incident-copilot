"""request_remediation records a proposal. execute_remediation runs only after a grant."""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, NoReturn

from incident_contracts.enums import ApprovalStatus, EventType, IncidentStatus, ToolClass
from incident_contracts.errors import DuplicateRemediationError, RemediationDeniedError
from incident_contracts.models import Approval, Incident, Proposal
from incident_contracts.service import IncidentService
from observability.logging import bind_context
from observability.tracing import (
    SPAN_REMEDIATION_EXECUTED,
    SPAN_REMEDIATION_PROPOSED,
    start_span,
)

from remediation_tool.actions import IAM_SCOPE, classify_action
from remediation_tool.runtime import RemediationTimeoutError, run_once
from remediation_tool.simulator import SimulatorState

LOGGER = logging.getLogger("remediation_tool")
DEFAULT_TTL_SECONDS = 900
DEFAULT_TIMEOUT_SECONDS = 3.0


class RemediationTools:
    """Safe-write boundary. The agent may request; only a granted approval may execute."""

    def __init__(
        self,
        service: IncidentService,
        *,
        simulator: SimulatorState | None = None,
        environ: Mapping[str, str] | None = None,
        clock: Any | None = None,
    ) -> None:
        env = os.environ if environ is None else environ
        self._service = service
        self._simulator = simulator if simulator is not None else SimulatorState()
        self._enabled = _bool(env, "REMEDIATION_ENABLED", default=True)
        self._ttl = timedelta(seconds=_int(env, "APPROVAL_TTL_SECONDS", DEFAULT_TTL_SECONDS))
        timeout_seconds = _int(env, "REMEDIATION_TIMEOUT_SECONDS", int(DEFAULT_TIMEOUT_SECONDS))
        self._timeout = float(timeout_seconds)
        self._clock = clock

    @property
    def simulator(self) -> SimulatorState:
        return self._simulator

    def request_remediation(
        self,
        payload: Mapping[str, Any],
        *,
        actor: str = "agent",
        at: datetime | None = None,
    ) -> dict[str, Any]:
        """Create a proposal and wait. This method does not change the simulator."""
        incident_id = str(payload.get("incident_id", ""))
        bind_context(incident_id=incident_id)
        with start_span(SPAN_REMEDIATION_PROPOSED, incident_id=incident_id):
            return self._request(payload, actor=actor, at=at)

    def _request(
        self,
        payload: Mapping[str, Any],
        *,
        actor: str,
        at: datetime | None,
    ) -> dict[str, Any]:
        action = str(payload.get("action", ""))
        classify_action(action)
        incident_id = str(payload.get("incident_id", ""))
        rationale = str(payload.get("rationale", "")).strip()
        if not rationale:
            raise ValueError("rationale is required")
        moment = self._now(at)
        incident = self._service.get(incident_id)
        if incident.proposal is not None or incident.status in {
            IncidentStatus.REMEDIATION_PROPOSED,
            IncidentStatus.AWAITING_APPROVAL,
            IncidentStatus.APPROVED,
            IncidentStatus.REMEDIATING,
        }:
            raise DuplicateRemediationError(
                f"incident {incident_id} already has an active remediation proposal"
            )
        proposal = Proposal(
            proposal_id=f"prop_{uuid.uuid4().hex[:16]}",
            incident_id=incident_id,
            action=action,
            rationale=rationale,
            requires_approval=True,
        )
        approval = Approval(
            approval_id=f"appr_{uuid.uuid4().hex[:16]}",
            incident_id=incident_id,
            proposal_id=proposal.proposal_id,
            status=ApprovalStatus.PENDING,
            actor=actor,
            created_at=moment,
            expires_at=moment + self._ttl,
        )
        digest = _digest(incident_id, proposal.proposal_id)
        self._service.propose_remediation(
            incident_id,
            actor=actor,
            at=moment,
            event_id=f"evt_prop_{digest}",
            action=action,
        )
        updated = self._service.request_approval(
            incident_id,
            approval,
            actor=actor,
            at=moment,
            event_id=f"evt_appr_{digest}",
            proposal=proposal,
        )
        self._audit_request(updated, proposal, approval)
        bind_context(incident_id=incident_id, approval_id=approval.approval_id)
        return {
            "tool": "request_remediation",
            "tool_class": ToolClass.SAFE_WRITE.value,
            "executed": False,
            "requires_approval": True,
            "proposal_id": proposal.proposal_id,
            "incident_id": incident_id,
            "action": action,
            "rationale": rationale,
            "status": updated.status.value,
            "approval_id": approval.approval_id,
            "expires_at": approval.expires_at.isoformat(),
        }

    def execute_remediation(
        self,
        incident_id: str,
        *,
        approval_id: str,
        idempotency_key: str,
        actor: str,
        at: datetime | None = None,
    ) -> Incident:
        """Apply the allowlisted simulator flag when the grant is valid and unexpired."""
        bind_context(incident_id=incident_id, approval_id=approval_id)
        with start_span(SPAN_REMEDIATION_EXECUTED, approval_id=approval_id):
            return self._execute(
                incident_id,
                approval_id=approval_id,
                idempotency_key=idempotency_key,
                actor=actor,
                at=at,
            )

    def _execute(
        self,
        incident_id: str,
        *,
        approval_id: str,
        idempotency_key: str,
        actor: str,
        at: datetime | None,
    ) -> Incident:
        if not idempotency_key.strip():
            raise ValueError("idempotency key is required")
        moment = self._now(at)
        digest = _digest(incident_id, idempotency_key)
        start_event = f"evt_rem_{digest}"
        done_event = f"evt_done_{digest}"
        if self._already_ran(incident_id, start_event):
            return self._service.get(incident_id)
        incident = self._service.get(incident_id)
        self._require_grant(incident, approval_id=approval_id, at=moment)
        if not self._enabled:
            self._deny(incident_id, "REMEDIATION_ENABLED=false; refusing remediation")
        proposal = incident.proposal
        if proposal is None:
            self._deny(incident_id, "remediation proposal is missing")
        classify_action(proposal.action)
        started = self._service.start_remediation(
            incident_id,
            actor=actor,
            at=moment,
            event_id=start_event,
            remediation_id=f"rem_{digest[:16]}",
            approval_id=approval_id,
        )
        try:
            applied = run_once(
                lambda: self._simulator.rollback(started.service, previous_version="previous"),
                timeout_seconds=self._timeout,
            )
        except RemediationTimeoutError:
            self._service.complete_remediation(
                incident_id,
                actor=actor,
                at=moment,
                event_id=done_event,
                success=False,
            )
            raise
        resolved = self._service.complete_remediation(
            incident_id,
            actor=actor,
            at=moment,
            event_id=done_event,
            success=True,
        )
        LOGGER.info(
            "remediation.executed",
            extra={
                "fields": {
                    "metric": "remediation_executed",
                    "incident_id": incident_id,
                    "approval_id": approval_id,
                    "action": proposal.action,
                    "actor": actor,
                    "at": moment.isoformat(),
                    "iam_scope": IAM_SCOPE,
                    "logical_version": applied["logical_version"],
                    "idempotency_key_present": True,
                }
            },
        )
        return resolved

    def _require_grant(self, incident: Incident, *, approval_id: str, at: datetime) -> None:
        approval = incident.approval
        if (
            approval is None
            or approval.approval_id != approval_id
            or approval.status is not ApprovalStatus.GRANTED
            or incident.status is not IncidentStatus.APPROVED
        ):
            self._deny(incident.incident_id, "valid approval_id is required to remediate")
        assert approval is not None
        if at > approval.expires_at:
            self._deny(incident.incident_id, f"approval {approval_id} has expired")

    def _deny(self, incident_id: str, message: str) -> NoReturn:
        LOGGER.warning(
            "remediation.denied",
            extra={
                "fields": {
                    "metric": "unauthorized_remediation",
                    "unauthorized_remediation": 1,
                    "decision": "DENIED",
                    "incident_id": incident_id,
                    "error": message,
                    "iam_scope": IAM_SCOPE,
                }
            },
        )
        raise RemediationDeniedError(message)

    def _already_ran(self, incident_id: str, event_id: str) -> bool:
        return any(event.event_id == event_id for event in self._service.events(incident_id))

    def _audit_request(self, incident: Incident, proposal: Proposal, approval: Approval) -> None:
        requested = [
            event
            for event in self._service.events(incident.incident_id)
            if event.event_type is EventType.APPROVAL_REQUESTED
        ]
        if not requested:
            raise RuntimeError("approval request was not recorded")
        LOGGER.info(
            "remediation.requested",
            extra={
                "fields": {
                    "incident_id": incident.incident_id,
                    "proposal_id": proposal.proposal_id,
                    "approval_id": approval.approval_id,
                    "action": proposal.action,
                    "executed": False,
                    "expires_at": approval.expires_at.isoformat(),
                }
            },
        )

    def _now(self, at: datetime | None) -> datetime:
        if at is not None:
            return at if at.tzinfo else at.replace(tzinfo=UTC)
        if self._clock is not None:
            current: datetime = self._clock()
            return current if current.tzinfo else current.replace(tzinfo=UTC)
        return datetime.now(UTC)


def attempt_remediation(
    tools: RemediationTools,
    incident_id: str,
    *,
    approval_id: str = "",
    idempotency_key: str = "missing-approval",
    actor: str = "human:demo",
    at: datetime | None = None,
) -> str:
    """Execute or return DENIED. Callers use this as the safety oracle."""
    try:
        tools.execute_remediation(
            incident_id,
            approval_id=approval_id,
            idempotency_key=idempotency_key,
            actor=actor,
            at=at,
        )
    except RemediationDeniedError:
        return "DENIED"
    return "EXECUTED"


def _digest(incident_id: str, key: str) -> str:
    return hashlib.sha256(f"{incident_id}:{key}".encode()).hexdigest()[:20]


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "")
    if raw == "":
        return default
    return int(raw)


def _bool(env: Mapping[str, str], key: str, *, default: bool) -> bool:
    raw = env.get(key, "")
    if raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

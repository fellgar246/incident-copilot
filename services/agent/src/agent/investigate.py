"""Start or replay an investigation and persist the diagnosis on the incident."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from cost_guardrails.estimator import estimate_cost_usd
from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import STOP_REASON, AppQuotas
from incident_contracts.enums import ActorKind, IncidentStatus
from incident_contracts.errors import IllegalTransitionError
from incident_contracts.models import Incident
from incident_contracts.service import IncidentService
from observability.logging import bind_context
from observability.metrics import record_metric
from observability.tracing import SPAN_INVESTIGATION_START, start_span
from remediation_tool.tools import RemediationTools

from agent.bedrock import invocation_enabled
from agent.loop import run_loop
from agent.model import LanguageModel
from agent.runs import AgentRunRecord, AgentRunStatus, AgentRunStore
from agent.sample import record_sampled_evaluation
from agent.session import session_from_quotas
from agent.tools import DeploymentTool, KnowledgeTool, LogTool, MetricTool, ToolDispatcher

ACTOR = ActorKind.AGENT.value


class InvestigationRejected(Exception):
    """The run was not started. `status_code` is the HTTP status the API should return."""

    def __init__(self, status_code: int, detail: dict[str, object]) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


def investigate(
    *,
    incident_id: str,
    correlation_id: str,
    idempotency_key: str,
    service: IncidentService,
    runs: AgentRunStore,
    quotas: AppQuotas,
    model: LanguageModel,
    logs: LogTool,
    metrics: MetricTool,
    deployments: DeploymentTool,
    knowledge: KnowledgeTool | None = None,
    now: datetime | None = None,
) -> AgentRunRecord:
    """Launch one investigation. The same idempotency key returns the existing run."""
    if not idempotency_key:
        raise InvestigationRejected(400, {"error": "Idempotency-Key is required"})
    session = session_from_quotas(quotas)
    del session
    moment = now or datetime.now(UTC)
    existing = runs.get_by_idempotency(incident_id, idempotency_key)
    if existing is not None:
        return existing

    incident = service.get(incident_id)
    if not invocation_enabled(quotas.ai_enabled, quotas.agent_invocation_enabled):
        raise InvestigationRejected(
            409,
            {
                "error": "agent invocation is disabled",
                "stop_reason": STOP_REASON,
            },
        )

    prior = runs.list_for_incident(incident_id)
    try:
        quotas.enforce(
            "MAX_AGENT_RUNS_PER_INCIDENT",
            used=len(prior),
            limit=quotas.max_agent_runs_per_incident,
        )
    except QuotaExceededError as exc:
        raise InvestigationRejected(
            429,
            {"error": str(exc), "stop_reason": exc.stop_reason, "quota_name": exc.quota_name},
        ) from exc

    if incident.status not in {
        IncidentStatus.DETECTED,
        IncidentStatus.QUEUED,
        IncidentStatus.INVESTIGATING,
    }:
        raise InvestigationRejected(
            409,
            {"error": f"cannot investigate from {incident.status.value}"},
        )

    run_id = f"run_{uuid.uuid4().hex[:16]}"
    record = AgentRunRecord(
        agent_run_id=run_id,
        incident_id=incident_id,
        correlation_id=correlation_id or incident.correlation_id,
        status=AgentRunStatus.QUEUED,
        model=model.model_id,
        idempotency_key=idempotency_key,
        created_at=moment,
        updated_at=moment,
    )
    runs.save(record)
    _enter_investigating(
        service,
        incident,
        run_id=run_id,
        correlation_id=record.correlation_id,
        at=moment,
    )
    record = record.model_copy(
        update={"status": AgentRunStatus.INVESTIGATING, "updated_at": moment}
    )
    runs.save(record)

    bind_context(
        incident_id=incident_id,
        correlation_id=record.correlation_id,
        agent_run_id=run_id,
    )
    dispatcher = ToolDispatcher(
        incidents=service,
        logs=logs,
        metrics=metrics,
        deployments=deployments,
        incident_id=incident_id,
        observed_at=incident.started_at,
        audit=service,
        agent_run_id=run_id,
        knowledge=knowledge,
        remediation=RemediationTools(service),
    )
    started = time.monotonic()
    with start_span(SPAN_INVESTIGATION_START, agent_run_id=run_id):
        result = run_loop(
            model=model,
            dispatcher=dispatcher,
            quotas=quotas,
            incident_id=incident_id,
            service=incident.service,
            observed_at=incident.started_at,
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    cost = estimate_cost_usd(
        model.model_id, result.budget.input_tokens, result.budget.output_tokens
    )
    finished = datetime.now(UTC) if now is None else moment
    if result.diagnosis is not None:
        service.record_diagnosis(
            incident_id,
            result.diagnosis,
            actor=ACTOR,
            at=finished,
            event_id=f"evt_{uuid.uuid4().hex[:16]}",
        )
        current = service.get(incident_id)
        service_incident = current.model_copy(
            update={
                "estimated_ai_cost_usd": round(
                    current.estimated_ai_cost_usd + cost.estimated_cost_usd, 8
                ),
                "agent_run_id": run_id,
            }
        )
        _save_incident(service, service_incident)
        _propose_when_required(service, incident_id, result.diagnosis, at=finished)
        status = AgentRunStatus.DIAGNOSED
        stop_reason = None
    elif result.stop_reason:
        status = AgentRunStatus.STOPPED
        stop_reason = result.stop_reason
    else:
        status = AgentRunStatus.FAILED
        stop_reason = None
    record = record.model_copy(
        update={
            "status": status,
            "model_calls": result.budget.model_calls,
            "input_tokens": result.budget.input_tokens,
            "output_tokens": result.budget.output_tokens,
            "tool_calls": result.budget.tool_calls,
            "rag_calls": result.budget.rag_calls,
            "runtime_ms": elapsed_ms,
            "estimated_cost_usd": cost.estimated_cost_usd,
            "stop_reason": stop_reason,
            "updated_at": finished,
            "tool_names": list(dispatcher.invoked),
        }
    )
    runs.save(record)
    _record_run_metrics(record)
    record_sampled_evaluation(
        incident_id=incident_id,
        rate=quotas.eval_sample_rate,
        diagnosis=result.diagnosis,
        cost_stopped=result.stop_reason is not None,
    )
    return record


def _propose_when_required(
    service: IncidentService,
    incident_id: str,
    diagnosis: object,
    *,
    at: datetime,
) -> None:
    """Record a SAFE_WRITE proposal when the diagnosis asks for a simulated rollback."""
    requires = bool(getattr(diagnosis, "requires_approval", False))
    action = str(getattr(diagnosis, "recommended_action", ""))
    cause = str(getattr(diagnosis, "probable_cause", "rollback"))
    if not requires or "rollback" not in action.lower():
        return
    RemediationTools(service).request_remediation(
        {
            "incident_id": incident_id,
            "action": "rollback_simulated",
            "rationale": cause[:500],
        },
        actor=ACTOR,
        at=at,
    )


def _enter_investigating(
    service: IncidentService,
    incident: Incident,
    *,
    run_id: str,
    correlation_id: str,
    at: datetime,
) -> None:
    current = incident
    if current.status is IncidentStatus.DETECTED:
        current = service.queue(
            current.incident_id,
            actor=ACTOR,
            at=at,
            event_id=f"evt_{uuid.uuid4().hex[:16]}",
        )
    if current.status is IncidentStatus.QUEUED:
        service.start_investigation(
            current.incident_id,
            actor=ACTOR,
            at=at,
            event_id=f"evt_{uuid.uuid4().hex[:16]}",
            agent_run_id=run_id,
            correlation_id=correlation_id,
        )


def _save_incident(service: IncidentService, incident: Incident) -> None:
    repository = getattr(service, "_repo", None)
    if repository is None or not hasattr(repository, "save"):
        return
    repository.save(incident)


def _record_run_metrics(record: AgentRunRecord) -> None:
    record_metric("llm_calls", record.model_calls)
    record_metric("input_tokens", record.input_tokens, unit="Count")
    record_metric("output_tokens", record.output_tokens, unit="Count")
    record_metric("agent_turns", record.model_calls)
    record_metric("tool_calls", record.tool_calls)
    record_metric("rag_calls", record.rag_calls)
    record_metric("investigation_latency", record.runtime_ms, unit="Milliseconds")
    record_metric("estimated_cost", record.estimated_cost_usd, unit="None")


def guard_illegal(exc: IllegalTransitionError) -> InvestigationRejected:
    return InvestigationRejected(409, {"error": str(exc)})

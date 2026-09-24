"""Model turns: tool requests or a final diagnosis document."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from incident_contracts.enums import EvidenceKind

from agent.parser import extract_json_object


@dataclass(frozen=True, slots=True)
class ToolRequest:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ModelTurn:
    input_tokens: int
    output_tokens: int
    tool_requests: tuple[ToolRequest, ...] = ()
    diagnosis_text: str | None = None


@dataclass
class ChatMessage:
    role: str
    content: str
    tool_name: str | None = None


class LanguageModel(Protocol):
    model_id: str

    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        max_output_tokens: int,
    ) -> ModelTurn: ...


def approximate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


class ScriptedInvestigator:
    """Local stand-in that gathers the allowlisted tools, then diagnoses from their text.

    Log and deployment text is evidence only. Phrases that name other tools are ignored.
    """

    model_id: str

    def __init__(self, model_id: str = "scripted-investigator") -> None:
        self.model_id = model_id
        self._planned = False

    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        max_output_tokens: int,
    ) -> ModelTurn:
        del system_prompt, max_output_tokens
        prompt_tokens = approximate_tokens("\n".join(item.content for item in messages))
        if not self._planned:
            self._planned = True
            service = _service_from_messages(messages)
            incident_id = _incident_id_from_messages(messages)
            requests = (
                ToolRequest("get_incident", {"incident_id": incident_id}),
                ToolRequest(
                    "query_logs",
                    {"service": service, "start_minutes_ago": 15, "limit": 20},
                ),
                ToolRequest(
                    "query_metrics",
                    {
                        "service": service,
                        "metric": "error_rate",
                        "start_minutes_ago": 60,
                    },
                ),
                ToolRequest(
                    "get_recent_deployments",
                    {"service": service, "lookback_hours": 24},
                ),
            )
            encoded = json.dumps([{"name": item.name} for item in requests])
            return ModelTurn(
                input_tokens=prompt_tokens,
                output_tokens=approximate_tokens(encoded),
                tool_requests=requests,
            )
        blob = "\n".join(item.content for item in messages if item.role == "tool")
        diagnosis = _diagnose(blob)
        text = json.dumps(diagnosis)
        return ModelTurn(
            input_tokens=prompt_tokens,
            output_tokens=approximate_tokens(text),
            diagnosis_text=text,
        )


def _incident_id_from_messages(messages: list[ChatMessage]) -> str:
    for message in messages:
        if '"incident_id"' not in message.content:
            continue
        try:
            payload = extract_json_object(message.content)
        except ValueError:
            continue
        incident_id = payload.get("incident_id")
        if isinstance(incident_id, str) and incident_id.startswith("inc_"):
            return incident_id
    return "inc_unknown"


def _service_from_messages(messages: list[ChatMessage]) -> str:
    for message in messages:
        if '"service"' in message.content:
            try:
                payload = extract_json_object(message.content)
            except ValueError:
                continue
            service = payload.get("service")
            if isinstance(service, str) and service:
                return service
    return "payments-api"


def _diagnose(blob: str) -> dict[str, Any]:
    lowered = blob.lower()
    if "upstream_timeout" in lowered or "deployment regression" in lowered:
        return _doc(
            summary="5xx and latency rose with a recent deploy.",
            probable_cause="Deployment regression: timeout/retry change causing UPSTREAM_TIMEOUT.",
            confidence=0.86,
            action="Simulated rollback of the current service to the previous version",
            requires_approval=True,
            evidence_summary="Error logs show repeated UPSTREAM_TIMEOUT after a recent deploy.",
            source="cloudwatch.logs",
            kind=EvidenceKind.OBSERVED,
            alternatives=["Regional dependency outage"],
        )
    if "pool_exhausted" in lowered:
        return _doc(
            summary="The service is waiting on database connections.",
            probable_cause="Connection pool exhaustion (POOL_EXHAUSTED).",
            confidence=0.84,
            action="Raise demo pool size by 1 (SAFE_WRITE) after approval",
            requires_approval=True,
            evidence_summary="Logs report POOL_EXHAUSTED while waiting for a connection.",
            source="cloudwatch.logs",
            kind=EvidenceKind.OBSERVED,
            alternatives=["Slow upstream queries"],
        )
    if "processing lag" in lowered or ("queue" in lowered and "backlog" in lowered):
        return _doc(
            summary="The worker is behind the enqueue rate.",
            probable_cause="Worker cannot keep up with enqueue rate.",
            confidence=0.8,
            action="Increase demo worker concurrency by 1 after approval",
            requires_approval=True,
            evidence_summary="Logs show processing lag increasing.",
            source="cloudwatch.logs",
            kind=EvidenceKind.OBSERVED,
            alternatives=["Poison message blocking the queue"],
        )
    return _doc(
        summary="Symptoms are brief or contradictory; there is not enough evidence for a fix.",
        probable_cause="Uncertain. Likely a transient signal rather than a confirmed fault.",
        confidence=0.28,
        action="Collect more evidence; do not remediate",
        requires_approval=False,
        evidence_summary="Available logs and metrics do not support a destructive or write action.",
        source="agent.hypothesis",
        kind=EvidenceKind.INFERENCE,
        alternatives=["Hidden error burst outside the log window"],
    )


def _doc(
    *,
    summary: str,
    probable_cause: str,
    confidence: float,
    action: str,
    requires_approval: bool,
    evidence_summary: str,
    source: str,
    kind: EvidenceKind,
    alternatives: list[str],
) -> dict[str, Any]:
    return {
        "summary": summary,
        "probable_cause": probable_cause,
        "confidence": confidence,
        "evidence": [
            {
                "kind": kind.value,
                "source": source,
                "summary": evidence_summary,
                "payload": {},
            }
        ],
        "retrieved_sources": [],
        "alternative_hypotheses": alternatives,
        "recommended_action": action,
        "requires_approval": requires_approval,
    }


@dataclass
class RecordingModel:
    """Test double that replays scripted turns and records every prompt it sees."""

    turns: list[ModelTurn]
    model_id: str = "recording-model"
    seen: list[str] = field(default_factory=list)

    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        max_output_tokens: int,
    ) -> ModelTurn:
        del system_prompt, max_output_tokens
        self.seen.append("\n".join(item.content for item in messages))
        if not self.turns:
            raise RuntimeError("recording model has no turns left")
        return self.turns.pop(0)

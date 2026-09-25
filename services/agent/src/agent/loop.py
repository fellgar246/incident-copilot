"""Turn loop. Stops on a diagnosis or on a usage guardrail without dropping the incident."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import AppQuotas
from incident_contracts.models import Diagnosis
from observability.tracing import SPAN_LLM_DIAGNOSIS, SPAN_LLM_REASONING, start_span

from agent.budget import RunBudget
from agent.model import ChatMessage, LanguageModel
from agent.parser import DiagnosisParseError, parse_diagnosis
from agent.prompt import SYSTEM_PROMPT
from agent.tools import ToolDispatcher, ToolError


@dataclass(frozen=True, slots=True)
class LoopResult:
    diagnosis: Diagnosis | None
    budget: RunBudget
    stop_reason: str | None
    error: str | None = None


def run_loop(
    *,
    model: LanguageModel,
    dispatcher: ToolDispatcher,
    quotas: AppQuotas,
    incident_id: str,
    service: str,
    observed_at: datetime,
) -> LoopResult:
    """Call the model until it diagnoses or a quota stops the run."""
    budget = RunBudget(quotas)
    messages = [
        ChatMessage(
            role="user",
            content=(
                f'{{"incident_id": "{incident_id}", "service": "{service}"}} '
                "Investigate this incident. Use only allowlisted tools."
            ),
        )
    ]
    try:
        while True:
            budget.ensure_can_continue()
            with start_span(SPAN_LLM_REASONING, incident_id=incident_id) as span:
                turn = model.complete(
                    system_prompt=SYSTEM_PROMPT,
                    messages=messages,
                    max_output_tokens=quotas.max_model_output_tokens_per_call,
                )
                if turn.diagnosis_text:
                    span.update_name(SPAN_LLM_DIAGNOSIS)
                span.set_attribute("input_tokens", turn.input_tokens)
                span.set_attribute("output_tokens", turn.output_tokens)
            budget.add_model_usage(turn.input_tokens, turn.output_tokens)
            if turn.diagnosis_text:
                diagnosis = parse_diagnosis(
                    turn.diagnosis_text,
                    observed_at=observed_at,
                    id_prefix=incident_id,
                )
                return LoopResult(diagnosis=diagnosis, budget=budget, stop_reason=None)
            if not turn.tool_requests:
                raise DiagnosisParseError("model returned neither tools nor a diagnosis")
            for request in turn.tool_requests:
                rag_calls_used = budget.rag_calls
                if request.name == "search_runbooks":
                    budget.add_rag_call()
                budget.add_tool_call()
                try:
                    body = dispatcher.dispatch(
                        request.name,
                        request.arguments,
                        calls_used=budget.tool_calls - 1,
                        rag_calls_used=rag_calls_used,
                    )
                except ToolError as exc:
                    body = json.dumps({"error": str(exc)})
                messages.append(ChatMessage(role="tool", content=body, tool_name=request.name))
    except QuotaExceededError as exc:
        return LoopResult(
            diagnosis=None,
            budget=budget,
            stop_reason=exc.stop_reason,
            error=exc.quota_name,
        )
    except DiagnosisParseError as exc:
        return LoopResult(diagnosis=None, budget=budget, stop_reason=None, error=str(exc))

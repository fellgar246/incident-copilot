"""Per-run quotas. Breaking one stops the run and keeps the incident."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import STOP_REASON, AppQuotas


@dataclass
class RunBudget:
    """Counters for one investigation. `started` is a monotonic timestamp."""

    quotas: AppQuotas
    started: float = field(default_factory=time.monotonic)
    turns: int = 0
    tool_calls: int = 0
    rag_calls: int = 0
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started

    def ensure_can_continue(self) -> None:
        self._check("MAX_AGENT_TURNS", self.turns, self.quotas.max_agent_turns)
        self._check("MAX_TOOL_CALLS_PER_RUN", self.tool_calls, self.quotas.max_tool_calls_per_run)
        self._check("MAX_RAG_CALLS_PER_RUN", self.rag_calls, self.quotas.max_rag_calls_per_run)
        if self.elapsed_seconds() >= self.quotas.max_session_seconds:
            raise QuotaExceededError(
                f"Quota MAX_SESSION_SECONDS reached ({self.quotas.max_session_seconds}s)",
                quota_name="MAX_SESSION_SECONDS",
                stop_reason=self.quotas.stop_reason,
            )

    def add_model_usage(self, input_tokens: int, output_tokens: int) -> None:
        if input_tokens > self.quotas.max_model_input_tokens_per_call:
            raise QuotaExceededError(
                "Quota MAX_MODEL_INPUT_TOKENS_PER_CALL reached",
                quota_name="MAX_MODEL_INPUT_TOKENS_PER_CALL",
                stop_reason=STOP_REASON,
            )
        if output_tokens > self.quotas.max_model_output_tokens_per_call:
            raise QuotaExceededError(
                "Quota MAX_MODEL_OUTPUT_TOKENS_PER_CALL reached",
                quota_name="MAX_MODEL_OUTPUT_TOKENS_PER_CALL",
                stop_reason=STOP_REASON,
            )
        self.model_calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.turns += 1

    def add_tool_call(self) -> None:
        self._check("MAX_TOOL_CALLS_PER_RUN", self.tool_calls, self.quotas.max_tool_calls_per_run)
        self.tool_calls += 1

    def add_rag_call(self) -> None:
        self._check("MAX_RAG_CALLS_PER_RUN", self.rag_calls, self.quotas.max_rag_calls_per_run)
        self.rag_calls += 1

    def _check(self, name: str, used: int, limit: int) -> None:
        self.quotas.enforce(name, used=used, limit=limit)

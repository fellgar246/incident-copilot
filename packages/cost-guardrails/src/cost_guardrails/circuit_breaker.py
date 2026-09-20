"""Global feature flags that stop AI spend without disabling read APIs."""

from __future__ import annotations

from dataclasses import dataclass

from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import STOP_REASON, AppQuotas


@dataclass(frozen=True, slots=True)
class CircuitBreaker:
    """Evaluates environment-level kill switches for AI, RAG, and remediation."""

    quotas: AppQuotas

    def assert_ai_enabled(self) -> None:
        if not self.quotas.ai_enabled:
            raise QuotaExceededError(
                "AI_ENABLED=false; refusing to generate AI spend",
                quota_name="AI_ENABLED",
                stop_reason=STOP_REASON,
            )

    def assert_agent_invocation_enabled(self) -> None:
        self.assert_ai_enabled()
        if not self.quotas.agent_invocation_enabled:
            raise QuotaExceededError(
                "AGENT_INVOCATION_ENABLED=false; refusing agent runs",
                quota_name="AGENT_INVOCATION_ENABLED",
                stop_reason=STOP_REASON,
            )

    def assert_rag_enabled(self) -> None:
        self.assert_ai_enabled()
        if not self.quotas.rag_enabled:
            raise QuotaExceededError(
                "RAG_ENABLED=false; refusing knowledge retrieval",
                quota_name="RAG_ENABLED",
                stop_reason=STOP_REASON,
            )

    def assert_remediation_enabled(self) -> None:
        if not self.quotas.remediation_enabled:
            raise QuotaExceededError(
                "REMEDIATION_ENABLED=false; refusing side-effecting actions",
                quota_name="REMEDIATION_ENABLED",
                stop_reason=STOP_REASON,
            )

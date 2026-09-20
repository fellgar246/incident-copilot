from __future__ import annotations

from pathlib import Path

import pytest
from cost_guardrails.circuit_breaker import CircuitBreaker
from cost_guardrails.envfile import parse_env_file
from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import STOP_REASON, load_quotas

ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"


def _quotas(**overrides: str) -> CircuitBreaker:
    env = parse_env_file(ENV_EXAMPLE)
    env.update(overrides)
    return CircuitBreaker(load_quotas(env))


def test_circuit_breaker_allows_when_enabled() -> None:
    breaker = _quotas()
    breaker.assert_ai_enabled()
    breaker.assert_agent_invocation_enabled()
    breaker.assert_rag_enabled()
    breaker.assert_remediation_enabled()


def test_ai_disabled_blocks_agent_and_rag() -> None:
    breaker = _quotas(AI_ENABLED="false")
    with pytest.raises(QuotaExceededError) as exc_info:
        breaker.assert_agent_invocation_enabled()
    assert exc_info.value.quota_name == "AI_ENABLED"
    assert exc_info.value.stop_reason == STOP_REASON


def test_rag_flag_independent_of_remediation() -> None:
    breaker = _quotas(RAG_ENABLED="false")
    with pytest.raises(QuotaExceededError, match="RAG_ENABLED"):
        breaker.assert_rag_enabled()
    breaker.assert_remediation_enabled()

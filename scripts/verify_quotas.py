"""Check that application quotas load and that the AI circuit breaker stops spend."""

from __future__ import annotations

import sys
from pathlib import Path

from cost_guardrails.circuit_breaker import CircuitBreaker
from cost_guardrails.envfile import parse_env_file
from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import STOP_REASON, load_quotas

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def main() -> int:
    quotas = load_quotas(parse_env_file(ENV_EXAMPLE))
    if quotas.target_monthly_cost_usd != 5.0:
        print("TARGET_MONTHLY_COST_USD must stay at 5 for dev", file=sys.stderr)
        return 2
    if quotas.max_incidents_per_day < 1:
        print("MAX_INCIDENTS_PER_DAY must be positive", file=sys.stderr)
        return 2
    breaker = CircuitBreaker(quotas)
    breaker.assert_ai_enabled()
    disabled = load_quotas(parse_env_file(ENV_EXAMPLE) | {"AI_ENABLED": "false"})
    try:
        CircuitBreaker(disabled).assert_agent_invocation_enabled()
    except QuotaExceededError as exc:
        if exc.stop_reason != STOP_REASON or exc.quota_name != "AI_ENABLED":
            print("circuit breaker stop reason mismatch", file=sys.stderr)
            return 2
    else:
        print("AI_ENABLED=false did not stop agent invocation", file=sys.stderr)
        return 2
    try:
        quotas.enforce(
            "MAX_AGENT_RUNS_PER_INCIDENT",
            used=quotas.max_agent_runs_per_incident,
            limit=quotas.max_agent_runs_per_incident,
        )
    except QuotaExceededError as exc:
        if exc.stop_reason != STOP_REASON:
            print("quota stop reason mismatch", file=sys.stderr)
            return 2
    else:
        print("a reached quota did not stop", file=sys.stderr)
        return 2
    print(
        "quotas ok "
        f"incidents/day={quotas.max_incidents_per_day} "
        f"runs/incident={quotas.max_agent_runs_per_incident} "
        f"turns={quotas.max_agent_turns} "
        f"ai_enabled={quotas.ai_enabled}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

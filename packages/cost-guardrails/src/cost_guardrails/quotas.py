"""Typed application quotas loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from cost_guardrails.exceptions import QuotaExceededError

STOP_REASON = "COST_OR_USAGE_GUARDRAIL"

REQUIRED_KEYS: tuple[str, ...] = (
    "AWS_REGION",
    "AI_ENABLED",
    "AGENT_INVOCATION_ENABLED",
    "RAG_ENABLED",
    "REMEDIATION_ENABLED",
    "TARGET_MONTHLY_COST_USD",
    "MAX_INCIDENTS_PER_DAY",
    "MAX_AGENT_RUNS_PER_INCIDENT",
    "MAX_AGENT_TURNS",
    "MAX_TOOL_CALLS_PER_RUN",
    "MAX_RAG_CALLS_PER_RUN",
    "MAX_RAG_RESULTS",
    "MAX_LOG_WINDOW_MINUTES",
    "MAX_LOG_RESULTS",
    "MAX_METRIC_WINDOW_MINUTES",
    "MAX_SESSION_SECONDS",
    "MAX_MODEL_INPUT_TOKENS_PER_CALL",
    "MAX_MODEL_OUTPUT_TOKENS_PER_CALL",
    "LOG_RETENTION_DAYS",
    "EVAL_SAMPLE_RATE",
)


def _require(env: Mapping[str, str], key: str) -> str:
    if key not in env or env[key] == "":
        raise KeyError(f"Missing required quota configuration: {key}")
    return env[key]


def _as_bool(raw: str, key: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean for {key}: {raw!r}")


def _as_int(raw: str, key: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {key}: {raw!r}") from exc
    if value < 0:
        raise ValueError(f"{key} must be >= 0, got {value}")
    return value


def _as_float(raw: str, key: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid float for {key}: {raw!r}") from exc
    if value < 0:
        raise ValueError(f"{key} must be >= 0, got {value}")
    return value


@dataclass(frozen=True, slots=True)
class AppQuotas:
    """Immutable quota set for a single environment."""

    aws_region: str
    ai_enabled: bool
    agent_invocation_enabled: bool
    rag_enabled: bool
    remediation_enabled: bool
    target_monthly_cost_usd: float
    max_incidents_per_day: int
    max_agent_runs_per_incident: int
    max_agent_turns: int
    max_tool_calls_per_run: int
    max_rag_calls_per_run: int
    max_rag_results: int
    max_log_window_minutes: int
    max_log_results: int
    max_metric_window_minutes: int
    max_session_seconds: int
    max_model_input_tokens_per_call: int
    max_model_output_tokens_per_call: int
    log_retention_days: int
    eval_sample_rate: float
    stop_reason: str = STOP_REASON

    def enforce(self, quota_name: str, used: int, limit: int) -> None:
        """Raise when `used` has already reached `limit`."""
        if used >= limit:
            raise QuotaExceededError(
                f"Quota {quota_name} reached ({used}/{limit})",
                quota_name=quota_name,
                stop_reason=self.stop_reason,
            )


def load_quotas(environ: Mapping[str, str] | None = None) -> AppQuotas:
    """Load quotas from `environ` or the process environment."""
    env = os.environ if environ is None else environ
    return AppQuotas(
        aws_region=_require(env, "AWS_REGION"),
        ai_enabled=_as_bool(_require(env, "AI_ENABLED"), "AI_ENABLED"),
        agent_invocation_enabled=_as_bool(
            _require(env, "AGENT_INVOCATION_ENABLED"), "AGENT_INVOCATION_ENABLED"
        ),
        rag_enabled=_as_bool(_require(env, "RAG_ENABLED"), "RAG_ENABLED"),
        remediation_enabled=_as_bool(_require(env, "REMEDIATION_ENABLED"), "REMEDIATION_ENABLED"),
        target_monthly_cost_usd=_as_float(
            _require(env, "TARGET_MONTHLY_COST_USD"), "TARGET_MONTHLY_COST_USD"
        ),
        max_incidents_per_day=_as_int(
            _require(env, "MAX_INCIDENTS_PER_DAY"), "MAX_INCIDENTS_PER_DAY"
        ),
        max_agent_runs_per_incident=_as_int(
            _require(env, "MAX_AGENT_RUNS_PER_INCIDENT"), "MAX_AGENT_RUNS_PER_INCIDENT"
        ),
        max_agent_turns=_as_int(_require(env, "MAX_AGENT_TURNS"), "MAX_AGENT_TURNS"),
        max_tool_calls_per_run=_as_int(
            _require(env, "MAX_TOOL_CALLS_PER_RUN"), "MAX_TOOL_CALLS_PER_RUN"
        ),
        max_rag_calls_per_run=_as_int(
            _require(env, "MAX_RAG_CALLS_PER_RUN"), "MAX_RAG_CALLS_PER_RUN"
        ),
        max_rag_results=_as_int(_require(env, "MAX_RAG_RESULTS"), "MAX_RAG_RESULTS"),
        max_log_window_minutes=_as_int(
            _require(env, "MAX_LOG_WINDOW_MINUTES"), "MAX_LOG_WINDOW_MINUTES"
        ),
        max_log_results=_as_int(_require(env, "MAX_LOG_RESULTS"), "MAX_LOG_RESULTS"),
        max_metric_window_minutes=_as_int(
            _require(env, "MAX_METRIC_WINDOW_MINUTES"), "MAX_METRIC_WINDOW_MINUTES"
        ),
        max_session_seconds=_as_int(_require(env, "MAX_SESSION_SECONDS"), "MAX_SESSION_SECONDS"),
        max_model_input_tokens_per_call=_as_int(
            _require(env, "MAX_MODEL_INPUT_TOKENS_PER_CALL"),
            "MAX_MODEL_INPUT_TOKENS_PER_CALL",
        ),
        max_model_output_tokens_per_call=_as_int(
            _require(env, "MAX_MODEL_OUTPUT_TOKENS_PER_CALL"),
            "MAX_MODEL_OUTPUT_TOKENS_PER_CALL",
        ),
        log_retention_days=_as_int(_require(env, "LOG_RETENTION_DAYS"), "LOG_RETENTION_DAYS"),
        eval_sample_rate=_as_float(_require(env, "EVAL_SAMPLE_RATE"), "EVAL_SAMPLE_RATE"),
    )

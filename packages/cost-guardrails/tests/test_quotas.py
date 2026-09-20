from __future__ import annotations

from pathlib import Path

import pytest
from cost_guardrails.envfile import parse_env_file
from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import REQUIRED_KEYS, STOP_REASON, load_quotas

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def test_env_example_contains_required_keys() -> None:
    parsed = parse_env_file(ENV_EXAMPLE)
    missing = [key for key in REQUIRED_KEYS if key not in parsed]
    assert missing == []


def test_load_quotas_from_env_example() -> None:
    quotas = load_quotas(parse_env_file(ENV_EXAMPLE))
    assert quotas.aws_region == "us-east-1"
    assert quotas.ai_enabled is True
    assert quotas.target_monthly_cost_usd == 5.0
    assert quotas.max_incidents_per_day == 10
    assert quotas.max_agent_runs_per_incident == 2
    assert quotas.max_agent_turns == 4
    assert quotas.max_tool_calls_per_run == 8
    assert quotas.max_rag_calls_per_run == 2
    assert quotas.max_rag_results == 4
    assert quotas.max_log_window_minutes == 15
    assert quotas.max_log_results == 100
    assert quotas.max_metric_window_minutes == 60
    assert quotas.max_session_seconds == 120
    assert quotas.max_model_input_tokens_per_call == 6000
    assert quotas.max_model_output_tokens_per_call == 1200
    assert quotas.log_retention_days == 7
    assert quotas.eval_sample_rate == 0.10
    assert quotas.stop_reason == STOP_REASON


def test_missing_key_raises() -> None:
    env = parse_env_file(ENV_EXAMPLE)
    del env["MAX_INCIDENTS_PER_DAY"]
    with pytest.raises(KeyError, match="MAX_INCIDENTS_PER_DAY"):
        load_quotas(env)


def test_invalid_bool_raises() -> None:
    env = parse_env_file(ENV_EXAMPLE)
    env["AI_ENABLED"] = "maybe"
    with pytest.raises(ValueError, match="AI_ENABLED"):
        load_quotas(env)


def test_enforce_quota_raises_with_stop_reason() -> None:
    quotas = load_quotas(parse_env_file(ENV_EXAMPLE))
    with pytest.raises(QuotaExceededError) as exc_info:
        quotas.enforce("MAX_INCIDENTS_PER_DAY", used=10, limit=quotas.max_incidents_per_day)
    assert exc_info.value.stop_reason == STOP_REASON
    assert exc_info.value.quota_name == "MAX_INCIDENTS_PER_DAY"


def test_eval_sample_rate_must_be_a_fraction() -> None:
    env = parse_env_file(ENV_EXAMPLE)
    env["EVAL_SAMPLE_RATE"] = "1.5"
    with pytest.raises(ValueError, match="EVAL_SAMPLE_RATE"):
        load_quotas(env)


def test_target_monthly_cost_must_be_positive() -> None:
    env = parse_env_file(ENV_EXAMPLE)
    env["TARGET_MONTHLY_COST_USD"] = "0"
    with pytest.raises(ValueError, match="TARGET_MONTHLY_COST_USD"):
        load_quotas(env)

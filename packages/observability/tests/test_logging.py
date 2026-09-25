from __future__ import annotations

import json
import logging

from observability.logging import (
    JsonLogFormatter,
    bind_context,
    clear_context,
    current_context,
    redact,
)


def test_redact_strips_bearer_tokens_and_access_keys() -> None:
    access_key = "AKIA" + ("X" * 16)
    payload = {
        "authorization": "Bearer super-secret",
        "note": "Authorization: Bearer abc.def",
        "aws_access_key_id": access_key,
        "nested": {"aws_secret_access_key": "not-a-real-secret-value"},
    }
    redacted = redact(payload)
    assert redacted["authorization"] == "[REDACTED]"
    assert "Bearer [REDACTED]" in redacted["note"]
    assert redacted["aws_access_key_id"] == "[REDACTED]"
    assert redacted["nested"]["aws_secret_access_key"] == "[REDACTED]"
    assert access_key not in json.dumps(redacted)


def test_json_formatter_includes_bound_context() -> None:
    clear_context()
    bind_context(
        request_id="req_1",
        correlation_id="cor_1",
        incident_id="inc_1",
        event_id="evt_1",
    )
    record = logging.LogRecord(
        name="api",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="incident.created",
        args=(),
        exc_info=None,
    )
    record.fields = {"authorization": "Bearer token-value", "service": "payments-api"}
    line = JsonLogFormatter().format(record)
    payload = json.loads(line)
    assert payload["request_id"] == "req_1"
    assert payload["correlation_id"] == "cor_1"
    assert payload["incident_id"] == "inc_1"
    assert payload["event_id"] == "evt_1"
    assert payload["service"] == "payments-api"
    assert payload["authorization"] == "[REDACTED]"
    assert "token-value" not in line
    clear_context()
    assert current_context() == {}


def test_formatter_redacts_prompts_and_tool_secrets() -> None:
    access_key = "AKIA" + ("Y" * 16)
    record = logging.LogRecord(
        name="agent",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="model turn",
        args=(),
        exc_info=None,
    )
    record.fields = {
        "prompt": f"system secret {access_key} Bearer raw-token",
        "system_prompt": "do not log this prompt",
        "tool_secret": "tool-credential",
        "agent_run_id": "run_1",
    }
    line = JsonLogFormatter().format(record)
    assert access_key not in line
    assert "raw-token" not in line
    assert "do not log this prompt" not in line
    assert "tool-credential" not in line
    payload = json.loads(line)
    assert payload["prompt"] == "[REDACTED]"
    assert payload["system_prompt"] == "[REDACTED]"
    assert payload["tool_secret"] == "[REDACTED]"
    assert payload["agent_run_id"] == "run_1"

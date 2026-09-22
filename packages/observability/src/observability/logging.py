"""JSON structured logging with correlation fields and secret redaction."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from observability.correlation import new_correlation_id

_REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)
_CORRELATION_ID: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_INCIDENT_ID: ContextVar[str | None] = ContextVar("incident_id", default=None)
_EVENT_ID: ContextVar[str | None] = ContextVar("event_id", default=None)

SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-amz-security-token",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "password",
        "secret",
        "token",
        "id_token",
        "refresh_token",
        "bearer",
        "private_key",
    }
)

_BEARER_RE = re.compile(r"bearer\s+\S+", re.IGNORECASE)
_AWS_KEY_RE = re.compile(r"AKIA[0-9A-Z]{16}")

_CONFIGURED = False


def bind_context(
    *,
    request_id: str | None = None,
    correlation_id: str | None = None,
    incident_id: str | None = None,
    event_id: str | None = None,
) -> None:
    """Attach identifiers to the current task so later log records inherit them."""
    if request_id is not None:
        _REQUEST_ID.set(request_id)
    if correlation_id is not None:
        _CORRELATION_ID.set(correlation_id)
    if incident_id is not None:
        _INCIDENT_ID.set(incident_id)
    if event_id is not None:
        _EVENT_ID.set(event_id)


def current_context() -> dict[str, str]:
    """Return the non-empty correlation fields bound to this task."""
    payload: dict[str, str] = {}
    request_id = _REQUEST_ID.get()
    correlation_id = _CORRELATION_ID.get()
    incident_id = _INCIDENT_ID.get()
    event_id = _EVENT_ID.get()
    if request_id:
        payload["request_id"] = request_id
    if correlation_id:
        payload["correlation_id"] = correlation_id
    if incident_id:
        payload["incident_id"] = incident_id
    if event_id:
        payload["event_id"] = event_id
    return payload


def clear_context() -> None:
    _REQUEST_ID.set(None)
    _CORRELATION_ID.set(None)
    _INCIDENT_ID.set(None)
    _EVENT_ID.set(None)


def redact(value: Any) -> Any:
    """Replace credentials, bearer tokens, and known secret field names."""
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        text = _BEARER_RE.sub("Bearer [REDACTED]", value)
        return _AWS_KEY_RE.sub("[REDACTED]", text)
    return value


class JsonLogFormatter(logging.Formatter):
    """Emit one JSON object per log record. Never include raw secrets."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self._safe_message(record),
        }
        payload.update(current_context())
        for field in ("request_id", "incident_id", "correlation_id", "event_id"):
            value = getattr(record, field, None)
            if value:
                payload[field] = value
        fields = getattr(record, "fields", None)
        if isinstance(fields, Mapping):
            payload.update(redact(dict(fields)))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)

    def _safe_message(self, record: logging.LogRecord) -> str:
        return str(redact(record.getMessage()))


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = current_context()
        for key, value in context.items():
            if not getattr(record, key, None):
                setattr(record, key, value)
        return True


def configure_json_logging(*, level: int = logging.INFO) -> None:
    """Install a process-wide JSON handler. Safe to call more than once."""
    global _CONFIGURED
    root = logging.getLogger()
    root.setLevel(level)
    if _CONFIGURED:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(ContextFilter())
    root.handlers = [handler]
    _CONFIGURED = True


def ensure_request_ids(
    *,
    request_id: str | None,
    correlation_id: str | None,
) -> tuple[str, str]:
    """Fill missing request/correlation identifiers with fresh UUIDs."""
    resolved_request = request_id or new_correlation_id()
    resolved_correlation = correlation_id or resolved_request
    return resolved_request, resolved_correlation

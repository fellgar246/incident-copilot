"""Redact secrets and keep a tool payload inside its byte budget."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

from observability.logging import redact

from deployments_tool.errors import ToolError

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(token|secret|password|api[_-]?key|session[_-]?token)\b\s*[:=]\s*\S+"
)


class _Dumpable(Protocol):
    def model_dump_json(self) -> str: ...


def redact_text(value: str) -> str:
    """Strip bearer tokens, access-key shapes, and token assignments from text."""
    cleaned = str(redact(value))
    return _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", cleaned)


def fit_items[T, R: _Dumpable](
    items: list[T],
    *,
    already_truncated: bool,
    max_bytes: int,
    build: Callable[[list[T], bool], R],
) -> R:
    """Drop the oldest items until the JSON payload fits. The envelope itself must fit."""
    chosen = list(items)
    truncated = already_truncated
    while True:
        result = build(chosen, truncated)
        if len(result.model_dump_json().encode()) <= max_bytes:
            return result
        if not chosen:
            raise ToolError("tool output envelope exceeds the byte cap")
        chosen.pop(0)
        truncated = True

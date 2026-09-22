"""Tool caps loaded from the same quota keys as the rest of the app."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

ABSOLUTE_MAX_OUTPUT_BYTES = 12 * 1024
DEFAULT_TIMEOUT_SECONDS = 3.0
DEFAULT_MAX_ATTEMPTS = 3


def _mapping(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    if environ is None:
        return os.environ
    return environ


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "")
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {key}: {raw!r}") from exc


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key, "")
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid float for {key}: {raw!r}") from exc


@dataclass(frozen=True, slots=True)
class ToolLimits:
    """Hard caps for one tool call. Output size cannot be configured above 12 KB."""

    max_log_window_minutes: int = 15
    max_log_results: int = 100
    max_metric_window_minutes: int = 60
    max_output_bytes: int = ABSOLUTE_MAX_OUTPUT_BYTES
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    max_tool_calls_per_run: int = 8

    def __post_init__(self) -> None:
        if not 1 <= self.max_log_window_minutes <= 15:
            raise ValueError("MAX_LOG_WINDOW_MINUTES must be between 1 and 15")
        if not 1 <= self.max_log_results <= 100:
            raise ValueError("MAX_LOG_RESULTS must be between 1 and 100")
        if not 1 <= self.max_metric_window_minutes <= 60:
            raise ValueError("MAX_METRIC_WINDOW_MINUTES must be between 1 and 60")
        if not 256 <= self.max_output_bytes <= ABSOLUTE_MAX_OUTPUT_BYTES:
            raise ValueError("MAX_TOOL_OUTPUT_BYTES must be between 256 and 12288")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 10:
            raise ValueError("TOOL_TIMEOUT_SECONDS must be in (0, 10]")
        if not 1 <= self.max_attempts <= DEFAULT_MAX_ATTEMPTS:
            raise ValueError("TOOL_MAX_ATTEMPTS must be between 1 and 3")
        if self.max_tool_calls_per_run < 1:
            raise ValueError("MAX_TOOL_CALLS_PER_RUN must be >= 1")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ToolLimits:
        """Load caps from the environment, falling back to the dev defaults."""
        env = _mapping(environ)
        return cls(
            max_log_window_minutes=_int(env, "MAX_LOG_WINDOW_MINUTES", 15),
            max_log_results=_int(env, "MAX_LOG_RESULTS", 100),
            max_metric_window_minutes=_int(env, "MAX_METRIC_WINDOW_MINUTES", 60),
            max_output_bytes=_int(env, "MAX_TOOL_OUTPUT_BYTES", ABSOLUTE_MAX_OUTPUT_BYTES),
            timeout_seconds=_float(env, "TOOL_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
            max_attempts=_int(env, "TOOL_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS),
            max_tool_calls_per_run=_int(env, "MAX_TOOL_CALLS_PER_RUN", 8),
        )

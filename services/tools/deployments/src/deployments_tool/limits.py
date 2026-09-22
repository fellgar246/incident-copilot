"""Caps for the deployments tool. The 12 KB ceiling matches the other evidence tools."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

ABSOLUTE_MAX_OUTPUT_BYTES = 12 * 1024
DEFAULT_TIMEOUT_SECONDS = 3.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_DEPLOYMENTS = 5
DEFAULT_MAX_LOOKBACK_HOURS = 72


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
    """Hard caps for one get_recent_deployments call."""

    max_deployments: int = DEFAULT_MAX_DEPLOYMENTS
    max_lookback_hours: int = DEFAULT_MAX_LOOKBACK_HOURS
    max_output_bytes: int = ABSOLUTE_MAX_OUTPUT_BYTES
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    max_tool_calls_per_run: int = 8

    def __post_init__(self) -> None:
        if not 1 <= self.max_deployments <= DEFAULT_MAX_DEPLOYMENTS:
            raise ValueError("MAX_RECENT_DEPLOYMENTS must be between 1 and 5")
        if not 1 <= self.max_lookback_hours <= DEFAULT_MAX_LOOKBACK_HOURS:
            raise ValueError("MAX_DEPLOYMENT_LOOKBACK_HOURS must be between 1 and 72")
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
            max_deployments=_int(env, "MAX_RECENT_DEPLOYMENTS", DEFAULT_MAX_DEPLOYMENTS),
            max_lookback_hours=_int(
                env, "MAX_DEPLOYMENT_LOOKBACK_HOURS", DEFAULT_MAX_LOOKBACK_HOURS
            ),
            max_output_bytes=_int(env, "MAX_TOOL_OUTPUT_BYTES", ABSOLUTE_MAX_OUTPUT_BYTES),
            timeout_seconds=_float(env, "TOOL_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
            max_attempts=_int(env, "TOOL_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS),
            max_tool_calls_per_run=_int(env, "MAX_TOOL_CALLS_PER_RUN", 8),
        )

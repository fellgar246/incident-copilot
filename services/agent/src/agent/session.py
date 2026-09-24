"""Session settings for a microVM runtime. Instance mode is not used."""

from __future__ import annotations

from dataclasses import dataclass

from cost_guardrails.quotas import AppQuotas

RUNTIME_MODE_MICROVM = "microvm"


@dataclass(frozen=True, slots=True)
class SessionConfig:
    """One investigation session. `runtime_mode` is always the microVM runtime."""

    max_session_seconds: int
    max_agent_turns: int
    max_tool_calls_per_run: int
    runtime_mode: str = RUNTIME_MODE_MICROVM

    def __post_init__(self) -> None:
        if self.runtime_mode != RUNTIME_MODE_MICROVM:
            raise ValueError("runtime mode must be microvm")
        if self.max_session_seconds <= 0:
            raise ValueError("max_session_seconds must be > 0")


def session_from_quotas(quotas: AppQuotas) -> SessionConfig:
    return SessionConfig(
        max_session_seconds=quotas.max_session_seconds,
        max_agent_turns=quotas.max_agent_turns,
        max_tool_calls_per_run=quotas.max_tool_calls_per_run,
    )

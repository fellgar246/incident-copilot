"""Allowlist for the one safe write. Anything else, including shell text, is denied."""

from __future__ import annotations

from incident_contracts.enums import ToolClass
from incident_contracts.errors import RemediationDeniedError

SAFE_ACTIONS: frozenset[str] = frozenset({"rollback_simulated"})

DESTRUCTIVE_ACTIONS: frozenset[str] = frozenset(
    {
        "restart_service",
        "delete_resource",
        "terminate_instance",
        "reboot_host",
        "run_shell",
    }
)

IAM_SCOPE = "remediation-tool-role"


def classify_action(action: str) -> ToolClass:
    """Return SAFE_WRITE for the allowlisted demo action. Every other name is denied."""
    if action in DESTRUCTIVE_ACTIONS or _looks_like_shell(action):
        raise RemediationDeniedError("DESTRUCTIVE actions are disabled")
    if action not in SAFE_ACTIONS:
        raise RemediationDeniedError(f"action is not allowlisted: {action}")
    return ToolClass.SAFE_WRITE


def _looks_like_shell(action: str) -> bool:
    if action != action.strip() or any(char.isspace() for char in action):
        return True
    return any(token in action for token in (";", "|", "&", "`", "$(", "\n", "\x00"))

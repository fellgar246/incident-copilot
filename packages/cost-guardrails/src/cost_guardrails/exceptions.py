"""Domain errors raised when a usage quota is exceeded."""

from __future__ import annotations


class QuotaExceededError(RuntimeError):
    """Raised when an application quota would generate further AI spend."""

    def __init__(self, message: str, *, quota_name: str, stop_reason: str) -> None:
        super().__init__(message)
        self.quota_name = quota_name
        self.stop_reason = stop_reason

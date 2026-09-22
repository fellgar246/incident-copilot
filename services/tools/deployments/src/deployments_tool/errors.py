"""Errors raised by the deployments evidence tool."""

from __future__ import annotations


class ToolError(RuntimeError):
    """Base error for a tool call that did not return evidence."""


class ToolValidationError(ToolError):
    """The tool input failed schema or allowlist validation."""


class AllowlistError(ToolValidationError):
    """The requested service is outside the demo allowlist."""


class ToolTimeoutError(ToolError):
    """The tool call exceeded its timeout."""


class TransientToolError(ToolError):
    """A retryable failure such as a throttle or a dropped connection."""


class ToolRetriesExhausted(ToolError):
    """Bounded retries were used up without a successful read."""

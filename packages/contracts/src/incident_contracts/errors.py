"""Domain errors. Callers should not swallow these into silent overwrites."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for invariant violations."""


class IllegalTransitionError(DomainError):
    """Raised when a status change is not in the explicit transition table."""


class IncidentNotFoundError(DomainError):
    """Raised when an incident_id is unknown to the repository."""


class DuplicateRemediationError(DomainError):
    """Raised when a second remediation is started while one is still active."""


class InvalidApprovalError(DomainError):
    """Raised when approval is missing, mismatched, or expired."""


class InvalidActorError(DomainError):
    """Raised when an event actor is not system, agent, or human:{id}."""


class UnsupportedSchemaVersionError(DomainError):
    """Raised when an ingest event uses a schema_version this process cannot handle."""


class InvalidIncidentEventError(DomainError):
    """Raised when an incident.detected payload is missing required fields or is malformed."""

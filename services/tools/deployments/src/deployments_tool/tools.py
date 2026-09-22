"""get_recent_deployments.

Returned payloads are untrusted data. Callers must not treat change summaries as instructions.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import STOP_REASON
from incident_contracts.enums import ToolClass
from incident_contracts.models import Deployment
from observability.logging import current_context

from deployments_tool.limits import ToolLimits
from deployments_tool.models import (
    DeploymentEvidenceItem,
    RecentDeploymentsInput,
    RecentDeploymentsResult,
)
from deployments_tool.runtime import bounded_call
from deployments_tool.sanitize import fit_items, redact_text
from deployments_tool.schemas import (
    parse_model,
    recent_deployments_input_schema,
    recent_deployments_output_schema,
    validate_output,
)
from deployments_tool.store import require_service

LOGGER = logging.getLogger("deployments_tool")
TOOL_CLASS = ToolClass.READ_ONLY
REQUIRES_APPROVAL = False


class DeploymentReader(Protocol):
    def query(self, *, service: str, since: datetime, limit: int) -> list[Deployment]: ...


class DeploymentTools:
    """Read-only deployment history for one demo service."""

    def __init__(self, store: DeploymentReader, *, limits: ToolLimits | None = None) -> None:
        self._store = store
        self._limits = limits or ToolLimits.from_env()

    def get_recent_deployments(
        self,
        payload: Any,
        *,
        now: datetime | None = None,
        calls_used: int | None = None,
    ) -> RecentDeploymentsResult:
        limits = self._limits
        request = parse_model(
            payload, recent_deployments_input_schema(limits), RecentDeploymentsInput
        )
        assert isinstance(request, RecentDeploymentsInput)
        require_service(request.service)
        self._enforce_budget(calls_used)
        end = _now(now)
        since = end - timedelta(hours=request.lookback_hours)
        rows = bounded_call(
            lambda: self._store.query(
                service=request.service,
                since=since,
                limit=limits.max_deployments + 1,
            ),
            timeout_seconds=limits.timeout_seconds,
            attempts=limits.max_attempts,
        )
        rows.sort(key=lambda item: item.deployed_at)
        truncated = len(rows) > limits.max_deployments
        capped = rows[-limits.max_deployments :]
        items = [_item(deployment) for deployment in capped]

        def build(
            chosen: list[DeploymentEvidenceItem], was_truncated: bool
        ) -> RecentDeploymentsResult:
            newest_first = list(reversed(chosen))
            return RecentDeploymentsResult(
                service=request.service,
                lookback_hours=request.lookback_hours,
                redacted=True,
                truncated=was_truncated,
                items=newest_first,
            )

        result = fit_items(
            items,
            already_truncated=truncated,
            max_bytes=limits.max_output_bytes,
            build=build,
        )
        validate_output(result, recent_deployments_output_schema(limits))
        LOGGER.info(
            "tool.completed",
            extra={
                "fields": {
                    "tool": "get_recent_deployments",
                    "service": request.service,
                    "items": len(result.items),
                    "truncated": result.truncated,
                    "redacted": True,
                    "model_invocations": 0,
                    **current_context(),
                }
            },
        )
        return result

    def _enforce_budget(self, calls_used: int | None) -> None:
        if calls_used is None:
            return
        limit = self._limits.max_tool_calls_per_run
        if calls_used >= limit:
            raise QuotaExceededError(
                f"Quota MAX_TOOL_CALLS_PER_RUN reached ({calls_used}/{limit})",
                quota_name="MAX_TOOL_CALLS_PER_RUN",
                stop_reason=STOP_REASON,
            )


def get_recent_deployments(
    payload: Any,
    *,
    store: DeploymentReader,
    now: datetime | None = None,
    limits: ToolLimits | None = None,
    calls_used: int | None = None,
) -> RecentDeploymentsResult:
    """Validate `payload` and return at most the five newest deployments in the lookback."""
    return DeploymentTools(store, limits=limits).get_recent_deployments(
        payload, now=now, calls_used=calls_used
    )


def _now(moment: datetime | None) -> datetime:
    if moment is None:
        return datetime.now(UTC)
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return moment.astimezone(UTC)


def _item(deployment: Deployment) -> DeploymentEvidenceItem:
    return DeploymentEvidenceItem(
        version=deployment.version,
        commit_sha=deployment.commit_sha,
        deployed_at=deployment.deployed_at,
        change_summary=redact_text(deployment.change_summary),
    )

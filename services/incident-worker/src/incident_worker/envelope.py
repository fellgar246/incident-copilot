"""Unwrap EventBridge and SQS envelopes into an incident.detected payload."""

from __future__ import annotations

import json
from typing import Any

from incident_contracts.errors import InvalidIncidentEventError


def unwrap_sqs_body(body: str) -> dict[str, Any]:
    """Parse an SQS body that may wrap the EventBridge event or the detail itself."""
    try:
        payload: Any = json.loads(body)
    except json.JSONDecodeError as exc:
        raise InvalidIncidentEventError("SQS body is not valid JSON") from exc
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise InvalidIncidentEventError("SQS body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise InvalidIncidentEventError("SQS body must be a JSON object")
    return _extract_detail(payload)


def _extract_detail(payload: dict[str, Any]) -> dict[str, Any]:
    detail = payload.get("detail")
    if isinstance(detail, dict) and ("event_id" in detail or "schema_version" in detail):
        return detail
    if isinstance(detail, str):
        try:
            nested = json.loads(detail)
        except json.JSONDecodeError as exc:
            raise InvalidIncidentEventError("EventBridge detail is not valid JSON") from exc
        if isinstance(nested, dict):
            return nested
    return payload

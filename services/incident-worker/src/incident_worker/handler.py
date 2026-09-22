"""Lambda handler for SQS-backed incident ingest."""

from __future__ import annotations

import logging
from typing import Any

from cost_guardrails.envfile import parse_env_file
from cost_guardrails.quotas import AppQuotas, load_quotas
from incident_contracts.events import parse_incident_detected
from incident_contracts.repository import IncidentRepository
from observability.logging import bind_context, clear_context, configure_json_logging

from incident_worker.envelope import unwrap_sqs_body
from incident_worker.processor import ingest_detected
from incident_worker.store import build_repository

logger = logging.getLogger("incident_worker")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """SQS event-source mapping entrypoint. Failed items are reported for retry/DLQ."""
    configure_json_logging()
    request_id = getattr(context, "aws_request_id", None)
    if isinstance(request_id, str):
        bind_context(request_id=request_id)
    try:
        return handle_records(event, repository=build_repository(), quotas=_load_quotas())
    finally:
        clear_context()


def handle_records(
    event: dict[str, Any],
    *,
    repository: IncidentRepository,
    quotas: AppQuotas | None = None,
) -> dict[str, Any]:
    """Process an SQS Lambda batch and return ReportBatchItemFailures."""
    failures: list[dict[str, str]] = []
    for record in event.get("Records", []):
        if not isinstance(record, dict):
            continue
        message_id = str(record.get("messageId") or "")
        try:
            body = record.get("body")
            if not isinstance(body, str):
                raise ValueError("SQS record is missing a string body")
            payload = unwrap_sqs_body(body)
            detected = parse_incident_detected(payload)
            ingest_detected(detected, repository=repository, quotas=quotas)
        except Exception:
            logger.exception(
                "incident.ingest_failed",
                extra={"fields": {"message_id": message_id}},
            )
            if message_id:
                failures.append({"itemIdentifier": message_id})
            else:
                raise
        finally:
            clear_context()
    return {"batchItemFailures": failures}


def _load_quotas() -> AppQuotas:
    try:
        return load_quotas()
    except KeyError:
        from pathlib import Path

        example = Path(__file__).resolve().parents[4] / ".env.example"
        return load_quotas(parse_env_file(example))

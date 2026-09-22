"""Incident ingest worker. Lambda entrypoint is incident_worker.handler.handler."""

from incident_worker.handler import handle_records, handler
from incident_worker.processor import ingest_detected

__all__ = ["handle_records", "handler", "ingest_detected"]

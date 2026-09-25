"""OpenTelemetry spans for one incident. CloudWatch and OTLP export the same names."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from threading import Lock
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Span, Status, StatusCode

from observability.logging import current_context, redact

LOGGER = logging.getLogger("observability.traces")

SPAN_INCIDENT_RECEIVED = "incident.received"
SPAN_INVESTIGATION_START = "investigation.start"
SPAN_LLM_REASONING = "llm.reasoning"
SPAN_LLM_DIAGNOSIS = "llm.diagnosis"
SPAN_REMEDIATION_PROPOSED = "remediation.proposed"
SPAN_REMEDIATION_EXECUTED = "remediation.executed"

STABLE_SPAN_NAMES: tuple[str, ...] = (
    SPAN_INCIDENT_RECEIVED,
    SPAN_INVESTIGATION_START,
    SPAN_LLM_REASONING,
    SPAN_LLM_DIAGNOSIS,
    SPAN_REMEDIATION_PROPOSED,
    SPAN_REMEDIATION_EXECUTED,
)

_LOCK = Lock()
_READY = False
_SPANS: dict[str, list[dict[str, Any]]] = {}


def tool_span_name(tool: str) -> str:
    """Stable dashboard name for one tool invocation."""
    return f"tool.{tool}"


class _MemorySpanExporter(SpanExporter):
    """Keep finished spans so an incident_id can rebuild the agent path."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            record = _span_record(span)
            incident_id = str(record["attributes"].get("incident_id") or "")
            if not incident_id:
                continue
            with _LOCK:
                _SPANS.setdefault(incident_id, []).append(record)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


class _CloudWatchSpanExporter(SpanExporter):
    """Write one JSON object per span. Lambda ships that line to CloudWatch Logs."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            LOGGER.info(json.dumps(redact(_span_record(span)), default=str))
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def configure_tracing(*, service_name: str = "ai-incident-copilot") -> None:
    """Install the tracer provider once. Later calls are ignored."""
    global _READY
    with _LOCK:
        if _READY:
            return
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(SimpleSpanProcessor(_MemorySpanExporter()))
        provider.add_span_processor(SimpleSpanProcessor(_CloudWatchSpanExporter()))
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
        if endpoint:
            _attach_otlp(provider, endpoint)
        trace.set_tracer_provider(provider)
        _READY = True


def reset_traces() -> None:
    """Drop stored spans. Used by tests that rebuild one incident."""
    with _LOCK:
        _SPANS.clear()


@contextmanager
def start_span(name: str, **attributes: str | int | float | bool) -> Iterator[Span]:
    """Open a span and copy the bound correlation identifiers onto it."""
    configure_tracing()
    merged: dict[str, str | int | float | bool] = {
        key: value for key, value in current_context().items()
    }
    for key, attr in attributes.items():
        merged[key] = attr
    tracer = trace.get_tracer("ai-incident-copilot")
    with tracer.start_as_current_span(name, attributes=merged) as span:
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            span.record_exception(exc)
            raise


def spans_for_incident(incident_id: str) -> list[dict[str, Any]]:
    """Return finished spans for one incident, oldest first."""
    with _LOCK:
        rows = list(_SPANS.get(incident_id, []))
    return sorted(rows, key=lambda item: int(item["start_time"]))


def reconstruct_trace(incident_id: str) -> dict[str, Any]:
    """Nest finished spans so the agent and tool path can be read from one id."""
    rows = spans_for_incident(incident_id)
    nodes = {
        row["span_id"]: {
            "name": row["name"],
            "span_id": row["span_id"],
            "parent_span_id": row["parent_span_id"],
            "attributes": row["attributes"],
            "children": [],
        }
        for row in rows
    }
    roots: list[dict[str, Any]] = []
    for node in nodes.values():
        parent = node["parent_span_id"]
        if parent and parent in nodes:
            nodes[parent]["children"].append(node)
        else:
            roots.append(node)
    return {"incident_id": incident_id, "spans": roots}


def _attach_otlp(provider: TracerProvider, endpoint: str) -> None:
    """Send the same spans to an OTLP endpoint when AgentCore observability is configured."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))


def _span_record(span: ReadableSpan) -> dict[str, Any]:
    parent = span.parent
    attributes = {str(key): value for key, value in (span.attributes or {}).items()}
    return {
        "name": span.name,
        "trace_id": format(span.context.trace_id, "032x"),
        "span_id": format(span.context.span_id, "016x"),
        "parent_span_id": format(parent.span_id, "016x") if parent is not None else None,
        "attributes": attributes,
        "start_time": span.start_time or 0,
        "end_time": span.end_time or 0,
        "status": span.status.status_code.name,
    }

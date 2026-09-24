"""Gateway client. The agent discovers and calls only the registered read-only tools."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import UTC, datetime
from typing import Any, Protocol

from incident_contracts.enums import ActorKind
from incident_contracts.gateway import (
    GATEWAY_SEARCH_ENABLED,
    TOOL_CALLS_METRIC,
    WEB_SEARCH_ENABLED,
    GatewayTool,
    ToolCalledV1,
    gateway_tool,
    gateway_tools,
)
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from observability.logging import redact

LOGGER = logging.getLogger("agent.gateway")
MAX_OUTPUT_BYTES = 12 * 1024
_FORMAT_CHECKER = Draft202012Validator.FORMAT_CHECKER

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


class ToolCallAudit(Protocol):
    def record_tool_called(
        self,
        incident_id: str,
        *,
        actor: str,
        at: datetime,
        event_id: str,
        payload: dict[str, object],
    ) -> Any: ...


class GatewayError(RuntimeError):
    """A tool name, argument, or output was rejected before it could widen access."""


class GatewayClient:
    """Invoke allowlisted tools and persist a TOOL_CALLED row for every attempt."""

    def __init__(
        self,
        handlers: dict[str, ToolHandler],
        *,
        audit: ToolCallAudit,
        incident_id: str,
        agent_run_id: str,
        max_tool_calls: int = 8,
    ) -> None:
        if GATEWAY_SEARCH_ENABLED or WEB_SEARCH_ENABLED:
            raise GatewayError("gateway search and web search are disabled")
        unknown = set(handlers) - {tool.name for tool in gateway_tools()}
        if unknown:
            raise GatewayError(f"refusing to register tools: {sorted(unknown)}")
        missing = [tool.name for tool in gateway_tools() if tool.name not in handlers]
        if missing:
            raise GatewayError(f"registered tools missing handlers: {missing}")
        self._handlers = dict(handlers)
        self._audit = audit
        self._incident_id = incident_id
        self._agent_run_id = agent_run_id
        self._max_tool_calls = max_tool_calls
        self.invoked: list[str] = []
        self.tool_calls = 0

    def discover(self) -> tuple[GatewayTool, ...]:
        """Return the authorized catalog. Unregistered names are not included."""
        return gateway_tools()

    def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        calls_used: int,
    ) -> dict[str, Any]:
        started = time.monotonic()
        if name not in self._handlers:
            self._log(
                name,
                arguments,
                _latency_ms(started),
                error="tool is not allowlisted",
                truncated=False,
            )
            raise GatewayError(f"tool is not allowlisted: {name}")
        tool = gateway_tool(name)
        if calls_used >= self._max_tool_calls:
            self._finish(
                tool.name,
                arguments,
                started,
                ok=False,
                truncated=False,
                error="MAX_TOOL_CALLS_PER_RUN",
            )
            raise GatewayError(
                f"MAX_TOOL_CALLS_PER_RUN reached ({calls_used}/{self._max_tool_calls})"
            )
        try:
            self._validate(arguments, tool.input_schema, label="input")
            self._reject_cross_incident(name, arguments)
            payload = _run_with_timeout(
                lambda: self._handlers[name](arguments),
                timeout_seconds=tool.timeout_seconds,
            )
            if not isinstance(payload, dict):
                raise GatewayError("tool output must be an object")
            truncated = bool(payload.get("truncated"))
            if len(json.dumps(payload, default=str).encode()) > MAX_OUTPUT_BYTES:
                raise GatewayError("output exceeded the byte cap")
            self._validate(payload, tool.output_schema, label="output")
        except GatewayError as exc:
            message = _safe_error(exc)
            self._finish(
                tool.name,
                arguments,
                started,
                ok=False,
                truncated="byte cap" in message,
                error=message,
            )
            raise
        except TimeoutError as exc:
            self._finish(
                tool.name, arguments, started, ok=False, truncated=False, error="tool timed out"
            )
            raise GatewayError("tool timed out") from exc
        except Exception as exc:
            message = _safe_error(exc)
            self._finish(tool.name, arguments, started, ok=False, truncated=False, error=message)
            raise GatewayError(message) from exc
        self.invoked.append(name)
        self.tool_calls += 1
        self._finish(
            tool.name,
            arguments,
            started,
            ok=True,
            truncated=truncated,
            error=None,
        )
        return payload

    def _reject_cross_incident(self, name: str, arguments: dict[str, Any]) -> None:
        if name != "get_incident":
            return
        requested = arguments.get("incident_id")
        if requested != self._incident_id:
            raise GatewayError("get_incident is scoped to the incident under investigation")

    def _finish(
        self,
        tool: str,
        arguments: dict[str, Any],
        started: float,
        *,
        ok: bool,
        truncated: bool,
        error: str | None,
    ) -> None:
        latency_ms = _latency_ms(started)
        body = ToolCalledV1(
            tool=tool,  # type: ignore[arg-type]
            ok=ok,
            latency_ms=latency_ms,
            truncated=truncated,
            error=error,
        )
        self._audit.record_tool_called(
            self._incident_id,
            actor=ActorKind.AGENT.value,
            at=datetime.now(UTC),
            event_id=f"evt_{uuid.uuid4().hex[:16]}",
            payload=body.model_dump(),
        )
        self._log(tool, arguments, latency_ms, error=error, truncated=truncated)

    def _log(
        self,
        tool: str,
        arguments: dict[str, Any],
        latency_ms: int,
        *,
        error: str | None,
        truncated: bool,
    ) -> None:
        LOGGER.info(
            "gateway.tool_called",
            extra={
                "fields": {
                    "metric": TOOL_CALLS_METRIC,
                    "tool_calls": 1,
                    "tool": tool,
                    "args": redact(arguments),
                    "latency_ms": latency_ms,
                    "error": error,
                    "incident_id": self._incident_id,
                    "agent_run_id": self._agent_run_id,
                    "truncated": truncated,
                }
            },
        )

    @staticmethod
    def _validate(payload: dict[str, Any], schema: dict[str, Any], *, label: str) -> None:
        validator = Draft202012Validator(schema, format_checker=_FORMAT_CHECKER)
        errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
        if errors:
            raise GatewayError(f"tool {label} rejected: {errors[0].message}")


def _safe_error(exc: BaseException) -> str:
    text = str(redact(str(exc)))
    return text[:300] if text else type(exc).__name__


def _latency_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def _run_with_timeout[T](fn: Callable[[], T], *, timeout_seconds: float) -> T:
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gateway-tool")
    future = pool.submit(fn)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError as exc:
        raise TimeoutError(f"tool call exceeded {timeout_seconds} seconds") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

"""Request correlation middleware and structured access logs."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from observability.logging import bind_context, clear_context, ensure_request_ids
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api")


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id, correlation_id = ensure_request_ids(
            request_id=request.headers.get("x-request-id"),
            correlation_id=request.headers.get("x-correlation-id"),
        )
        bind_context(
            request_id=request_id,
            correlation_id=correlation_id,
            incident_id=_incident_id_from_path(request.url.path),
            agent_run_id=request.headers.get("x-agent-run-id"),
            approval_id=request.headers.get("x-approval-id"),
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={"fields": {"method": request.method, "path": request.url.path}},
            )
            raise
        else:
            logger.info(
                "request_completed",
                extra={
                    "fields": {
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                    }
                },
            )
            response.headers["x-request-id"] = request_id
            response.headers["x-correlation-id"] = correlation_id
            return response
        finally:
            clear_context()


def _incident_id_from_path(path: str) -> str | None:
    parts = [item for item in path.split("/") if item]
    if len(parts) >= 2 and parts[0] == "incidents" and parts[1] not in {"simulate"}:
        return parts[1]
    return None

"""MicroVM entrypoint. Each payload carries incident_id and correlation_id."""

from __future__ import annotations

from typing import Any

from agent.investigate import InvestigationRejected, investigate
from agent.session import RUNTIME_MODE_MICROVM


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Invoke one investigation. `context` is unused; the host supplies the deadline."""
    del context
    if event.get("runtime_mode", RUNTIME_MODE_MICROVM) != RUNTIME_MODE_MICROVM:
        return {"ok": False, "error": "runtime mode must be microvm"}
    incident_id = event.get("incident_id")
    correlation_id = event.get("correlation_id")
    if not isinstance(incident_id, str) or not incident_id:
        return {"ok": False, "error": "incident_id is required"}
    if not isinstance(correlation_id, str) or not correlation_id:
        return {"ok": False, "error": "correlation_id is required"}
    dependencies = event.get("dependencies")
    if not isinstance(dependencies, dict):
        return {"ok": False, "error": "dependencies are required"}
    try:
        record = investigate(
            incident_id=incident_id,
            correlation_id=correlation_id,
            idempotency_key=str(event.get("idempotency_key") or incident_id),
            service=dependencies["service"],
            runs=dependencies["runs"],
            quotas=dependencies["quotas"],
            model=dependencies["model"],
            logs=dependencies["logs"],
            metrics=dependencies["metrics"],
            deployments=dependencies["deployments"],
        )
    except InvestigationRejected as exc:
        return {"ok": False, "error": exc.detail}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
    return {
        "ok": True,
        "runtime_mode": RUNTIME_MODE_MICROVM,
        "agent_run": record.model_dump(mode="json"),
    }

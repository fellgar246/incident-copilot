from __future__ import annotations

import json

from incident_contracts.enums import ScenarioId

from simulator import emit_metric_points, emit_structured_logs, simulate


def test_structured_logs_keep_level_message_and_service() -> None:
    fixture = simulate(ScenarioId.DEPLOYMENT_REGRESSION, seed="golden")
    lines = emit_structured_logs(fixture)
    assert len(lines) == len(fixture.telemetry.logs)
    payload = json.loads(lines[0])
    assert payload["service"] == "payments-api"
    assert payload["level"] == "ERROR"
    assert "UPSTREAM_TIMEOUT" in payload["message"]
    points = emit_metric_points(fixture)
    names = {item["name"] for item in points}
    assert "5xx_rate" in names
    assert "latency_p95" in names

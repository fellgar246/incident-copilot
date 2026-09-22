from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from incident_contracts.enums import ScenarioId

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_seed() -> Any:
    path = REPO_ROOT / "scripts" / "seed_telemetry.py"
    spec = importlib.util.spec_from_file_location("seed_telemetry", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_report_contains_fixture_evidence(capsys: Any) -> None:
    seed = _load_seed()
    assert seed.main(["deployment_regression", "--seed", "golden"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["scenario"] == ScenarioId.DEPLOYMENT_REGRESSION.value
    assert report["published_cloudwatch"] is False
    blob = json.dumps(report)
    assert "UPSTREAM_TIMEOUT" in blob
    assert "2026.09.20.3" in blob
    assert report["query_logs"]["untrusted"] is True
    assert report["query_logs"]["tool_class"] == "READ_ONLY"


def test_put_cloudwatch_uses_the_publisher(monkeypatch: Any, capsys: Any) -> None:
    seed = _load_seed()
    calls: list[str] = []

    def fake_publish(fixture: Any) -> None:
        calls.append(fixture.scenario.value)

    monkeypatch.setattr(seed, "publish_cloudwatch", fake_publish)
    assert seed.main(["--all", "--put-cloudwatch", "--seed", "golden"]) == 0
    assert calls == [item.value for item in ScenarioId]
    assert capsys.readouterr().out.count("\n") == 4

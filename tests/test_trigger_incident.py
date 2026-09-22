from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from incident_contracts.enums import ScenarioId
from incident_contracts.events import parse_incident_detected
from incident_contracts.repository import InMemoryIncidentRepository

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_trigger() -> Any:
    path = REPO_ROOT / "scripts" / "trigger_incident.py"
    spec = importlib.util.spec_from_file_location("trigger_incident", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json_stream(text: str) -> list[dict[str, object]]:
    decoder = json.JSONDecoder()
    items: list[dict[str, object]] = []
    idx = 0
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        obj, offset = decoder.raw_decode(text[idx:])
        assert isinstance(obj, dict)
        items.append(obj)
        idx += offset
    return items


def test_trigger_prints_versioned_event_for_each_scenario(capsys: object) -> None:
    trigger = _load_trigger()
    assert trigger.main(["--all", "--seed", "cli"]) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    blobs = _load_json_stream(captured.out)
    assert len(blobs) == 4
    scenarios = {item["scenario"] for item in blobs}
    assert scenarios == {item.value for item in ScenarioId}
    for item in blobs:
        parsed = parse_incident_detected(item)
        assert parsed.correlation_id
        assert parsed.event_id.startswith("evt_")


def test_trigger_ingest_local_is_idempotent(monkeypatch: object) -> None:
    trigger = _load_trigger()
    repository = InMemoryIncidentRepository()

    def fake_build_repository() -> InMemoryIncidentRepository:
        return repository

    import incident_worker.store as store

    monkeypatch.setattr(store, "build_repository", fake_build_repository)  # type: ignore[attr-defined]
    first = trigger.main(["deployment_regression", "--seed", "once", "--ingest-local"])
    second = trigger.main(["deployment_regression", "--seed", "once", "--ingest-local"])
    assert first == second == 0
    assert len(repository.list_incidents()) == 1
    incident = repository.list_incidents()[0]
    assert incident.correlation_id
    assert incident.source_event_id

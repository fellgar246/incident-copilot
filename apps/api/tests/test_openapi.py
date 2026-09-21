from __future__ import annotations

import json
from pathlib import Path

from api.main import create_app
from fastapi.testclient import TestClient

OPENAPI_PATH = Path(__file__).resolve().parents[1] / "openapi.json"

SLICE_PATHS = {
    ("GET", "/health"),
    ("GET", "/health/aws"),
    ("GET", "/incidents"),
    ("POST", "/incidents/simulate"),
    ("GET", "/incidents/{id}"),
    ("GET", "/incidents/{id}/events"),
}


def test_openapi_slice_contract_is_stable() -> None:
    spec = create_app().openapi()
    committed = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    live_ops = {
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method in operations
        if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    }
    committed_ops = {
        (method.upper(), path)
        for path, operations in committed["paths"].items()
        for method in operations
        if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    }
    assert SLICE_PATHS <= live_ops
    assert SLICE_PATHS <= committed_ops
    simulate = spec["paths"]["/incidents/simulate"]["post"]
    assert "201" in simulate["responses"]
    assert "200" in simulate["responses"]
    assert "422" in simulate["responses"]
    parameters = simulate.get("parameters") or []
    assert any(item.get("name") == "Idempotency-Key" for item in parameters)
    get_incident = spec["paths"]["/incidents/{id}"]["get"]
    assert "404" in get_incident["responses"]


def test_openapi_snapshot_matches_app() -> None:
    spec = create_app().openapi()
    committed = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    assert spec["paths"].keys() == committed["paths"].keys()
    for path in SLICE_PATHS:
        method, route = path
        assert method.lower() in committed["paths"][route]


def test_client_exposes_slice_routes(client: TestClient) -> None:
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    assert "/health" in paths
    assert "/incidents/simulate" in paths
    assert "/incidents/{id}/events" in paths

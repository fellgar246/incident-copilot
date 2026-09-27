"""Post-deploy smoke: health, simulate, optional investigate, and a denied remediation.

Pass --dry-run to print the calls without contacting the API.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

ACTOR = "human:demo"


def _request(
    method: str,
    url: str,
    *,
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
) -> tuple[int, dict[str, object]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("accept", "application/json")
    if payload is not None:
        request.add_header("content-type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            if not isinstance(parsed, dict):
                parsed = {"value": parsed}
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"error": raw}
        if not isinstance(parsed, dict):
            parsed = {"value": parsed}
        return exc.code, parsed


def _health(base_url: str) -> None:
    last_error = "health did not become ready"
    for _ in range(5):
        try:
            status, body = _request("GET", f"{base_url}/health", timeout=10)
        except urllib.error.URLError as exc:
            last_error = str(exc)
            continue
        if status == 200 and body.get("status") == "ok":
            return
        last_error = f"health status {status}"
    raise RuntimeError(last_error)


def run_smoke(base_url: str, *, investigate: bool) -> None:
    root = base_url.rstrip("/")
    _health(root)
    status, created = _request(
        "POST",
        f"{root}/incidents/simulate",
        payload={"scenario": "deployment_regression", "seed": "smoke"},
    )
    if status not in {200, 201}:
        raise RuntimeError(f"simulate failed: {status} {created}")
    incident_id = str(created["incident_id"])
    read_status, _incident = _request("GET", f"{root}/incidents/{incident_id}")
    if read_status != 200:
        raise RuntimeError(f"read incident failed: {read_status}")
    costs_status, _costs = _request("GET", f"{root}/metrics/costs")
    if costs_status != 200:
        raise RuntimeError(f"costs failed: {costs_status}")
    if not investigate:
        print(f"smoke passed (reads only) incident_id={incident_id}")
        return
    investigated, run = _request(
        "POST",
        f"{root}/incidents/{incident_id}/investigate",
        headers={"Idempotency-Key": "smoke-investigate"},
        timeout=60,
    )
    if investigated == 409:
        print(f"smoke passed (AI disabled, reads ok) incident_id={incident_id}")
        return
    if investigated not in {200, 201}:
        raise RuntimeError(f"investigate failed: {investigated} {run}")
    approval_id = str(
        _request("GET", f"{root}/incidents/{incident_id}")[1].get("approval_id") or ""
    )
    if approval_id == "":
        raise RuntimeError("investigation did not record an approval_id")
    denied, denial = _request(
        "POST",
        f"{root}/incidents/{incident_id}/remediate",
        payload={"approval_id": approval_id},
        headers={"Idempotency-Key": "smoke-deny", "X-Actor": ACTOR},
    )
    detail = denial.get("detail")
    decision = detail.get("decision") if isinstance(detail, dict) else None
    if denied != 403 or decision != "DENIED":
        raise RuntimeError(f"unapproved remediation was not denied: {denied} {denial}")
    approved, _approval = _request(
        "POST",
        f"{root}/incidents/{incident_id}/approve",
        payload={"approval_id": approval_id},
        headers={"Idempotency-Key": "smoke-approve", "X-Actor": ACTOR},
    )
    if approved not in {200, 201}:
        raise RuntimeError(f"approve failed: {approved}")
    executed, execution = _request(
        "POST",
        f"{root}/incidents/{incident_id}/remediate",
        payload={"approval_id": approval_id},
        headers={"Idempotency-Key": "smoke-execute", "X-Actor": ACTOR},
    )
    if executed not in {200, 201} or execution.get("status") != "RESOLVED":
        raise RuntimeError(f"approved remediation failed: {executed} {execution}")
    print(f"smoke passed incident_id={incident_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-investigate", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print("dry-run: GET /health")
        print("dry-run: POST /incidents/simulate")
        print("dry-run: GET /incidents/{id}")
        print("dry-run: GET /metrics/costs")
        if args.skip_investigate:
            print("dry-run: investigate skipped")
        else:
            print("dry-run: POST /incidents/{id}/investigate when AI is enabled")
            print("dry-run: POST /incidents/{id}/remediate expect 403")
            print("dry-run: POST /incidents/{id}/approve")
            print("dry-run: POST /incidents/{id}/remediate expect RESOLVED")
        return 0
    if args.base_url == "":
        print("--base-url is required unless --dry-run is set", file=sys.stderr)
        return 2
    try:
        run_smoke(args.base_url, investigate=not args.skip_investigate)
    except (RuntimeError, urllib.error.URLError, KeyError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

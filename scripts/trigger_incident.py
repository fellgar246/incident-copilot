#!/usr/bin/env python3
"""Build, print, locally ingest, or publish incident.detected.v1 for the demo scenarios."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from incident_contracts.enums import ScenarioId
from incident_contracts.events import (
    DEFAULT_EVENT_SOURCE,
    INCIDENT_DETECTED_DETAIL_TYPE,
    detected_event_from_fixture,
)

from simulator import simulate


def build_event(scenario: ScenarioId | str, seed: str) -> dict[str, object]:
    fixture = simulate(scenario, seed=seed)
    return detected_event_from_fixture(fixture).model_dump(mode="json", exclude_none=True)


def ingest_local(payload: dict[str, object]) -> str:
    from incident_contracts.events import parse_incident_detected
    from incident_worker.processor import ingest_detected
    from incident_worker.store import build_repository

    incident = ingest_detected(parse_incident_detected(payload), repository=build_repository())
    return incident.incident_id


def put_events(payload: dict[str, object], *, bus_name: str, source: str) -> str:
    import boto3  # type: ignore[import-untyped]

    client = boto3.client("events", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    response = client.put_events(
        Entries=[
            {
                "Source": source,
                "DetailType": INCIDENT_DETECTED_DETAIL_TYPE,
                "Detail": json.dumps(payload),
                "EventBusName": bus_name,
            }
        ]
    )
    entries = response.get("Entries") or []
    event_id = entries[0].get("EventId") if entries else None
    if not event_id or response.get("FailedEntryCount"):
        raise RuntimeError(f"EventBridge PutEvents failed: {response}")
    return str(event_id)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario",
        nargs="?",
        default=ScenarioId.DEPLOYMENT_REGRESSION.value,
        choices=[item.value for item in ScenarioId],
    )
    parser.add_argument("--seed", default="demo")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Emit all four demo scenarios instead of a single one.",
    )
    parser.add_argument(
        "--ingest-local",
        action="store_true",
        help="Run the worker ingest path in-process (memory or DynamoDB from env).",
    )
    parser.add_argument(
        "--put-events",
        action="store_true",
        help="Publish to EventBridge. Requires EVENT_BUS_NAME or --bus.",
    )
    parser.add_argument("--bus", default=os.environ.get("EVENT_BUS_NAME", "").strip())
    parser.add_argument(
        "--source",
        default=os.environ.get("EVENT_SOURCE", DEFAULT_EVENT_SOURCE).strip()
        or DEFAULT_EVENT_SOURCE,
    )
    args = parser.parse_args(argv)

    scenarios = list(ScenarioId) if args.all else [ScenarioId(args.scenario)]
    for scenario in scenarios:
        payload = build_event(scenario, args.seed)
        if args.put_events:
            if not args.bus:
                parser.error("EVENT_BUS_NAME or --bus is required with --put-events")
            bus_id = put_events(payload, bus_name=args.bus, source=args.source)
            print(json.dumps({"published": True, "event_bridge_id": bus_id, **payload}))
            continue
        if args.ingest_local:
            incident_id = ingest_local(payload)
            print(json.dumps({"ingested": True, "incident_id": incident_id, **payload}))
            continue
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

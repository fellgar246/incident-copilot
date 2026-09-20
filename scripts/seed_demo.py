#!/usr/bin/env python3
"""Print a deterministic incident fixture as JSON. No AWS calls."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from incident_contracts.enums import ScenarioId

from simulator import simulate

REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario",
        nargs="?",
        default=ScenarioId.DEPLOYMENT_REGRESSION.value,
        choices=[item.value for item in ScenarioId],
    )
    parser.add_argument("--seed", default="golden")
    parser.add_argument(
        "--write-golden",
        action="store_true",
        help="Write all four golden fixtures under fixtures/incidents/",
    )
    args = parser.parse_args(argv)

    if args.write_golden:
        out_dir = REPO_ROOT / "fixtures" / "incidents"
        out_dir.mkdir(parents=True, exist_ok=True)
        for scenario in ScenarioId:
            fixture = simulate(scenario, seed=args.seed)
            path = out_dir / f"{scenario.value}.json"
            path.write_text(fixture.model_dump_json(indent=2) + "\n", encoding="utf-8")
            print(path)
        return 0

    fixture = simulate(args.scenario, seed=args.seed)
    sys.stdout.write(fixture.model_dump_json(indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

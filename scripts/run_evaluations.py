#!/usr/bin/env python3
"""Run the offline evaluation suite and exit non-zero when a gate fails."""

from __future__ import annotations

import argparse
import json

from evaluations.dataset import PROFILES
from evaluations.runner import failed_gates, run_suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="pr")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Opt into a quota-capped run. Requires EVAL_LIVE=1. Does not call a model vendor.",
    )
    args = parser.parse_args(argv)
    summary = run_suite(profile=args.profile, live=args.live)
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "profile",
                    "case_count",
                    "evaluation_pass_rate",
                    "diagnosis_accuracy",
                    "required_evidence_recall",
                    "groundedness",
                    "unsafe_action_count",
                    "unsafe_action_rate",
                    "p95_agent_turns",
                    "avg_tool_calls",
                    "avg_estimated_cost",
                    "cost_per_successful_diagnosis",
                    "estimated_cost_usd",
                    "passed",
                )
            },
            indent=2,
        )
    )
    failed = failed_gates(summary)
    if failed:
        print("failed gates: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

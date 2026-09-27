"""Print the observed demo-session estimate and the monthly design envelope.

Figures are list prices or design targets. They are not an AWS invoice.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAST_RUN = REPO_ROOT / "evals" / "expected" / "last_run.json"

# Design envelope for one dev month. Not a quote.
DESIGN_ENVELOPE_USD: tuple[tuple[str, str], ...] = (
    ("Lambda, API, SQS, EventBridge, DynamoDB, S3", "0-0.50"),
    ("CloudWatch", "0-0.75"),
    ("Managed knowledge base storage", "0.05-0.25"),
    ("Managed knowledge base retrieval", "0.05-0.50"),
    ("AgentCore Gateway", "0.01-0.10"),
    ("AgentCore Runtime", "0.10-1.00"),
    ("Bedrock inference", "0.50-2.50"),
    ("Evaluations", "0.05-0.50"),
)

MITIGATION_ORDER: tuple[str, ...] = (
    "Turn off continuous evaluations.",
    "Lower the daily incident cap.",
    "Lower MAX_AGENT_TURNS.",
    "Lower tool calls and prompt context.",
    "Lower the number of logs consulted.",
    "Switch to a cheaper model.",
    "Turn RAG off outside test sessions.",
    "Review Cost Explorer before continuing.",
)


def load_observed(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "demo_session_usd": float(payload["cost_per_successful_diagnosis"]),
        "full_suite_usd": float(payload["estimated_cost_usd"]),
        "avg_run_usd": float(payload["avg_estimated_cost"]),
    }


def render(observed: dict[str, float], *, model: str, input_tokens: int, output_tokens: int) -> str:
    from cost_guardrails.estimator import estimate_cost_usd

    ad_hoc = estimate_cost_usd(model, input_tokens, output_tokens)
    lines = [
        "Demo session: deployment_regression",
        f"observed_estimated_usd: {observed['demo_session_usd']:.8f}",
        "source: offline evaluation list-price tokens, not an AWS invoice",
        f"full_offline_suite_usd: {observed['full_suite_usd']:.8f}",
        f"avg_run_usd: {observed['avg_run_usd']:.8f}",
        "",
        f"Ad hoc estimate ({ad_hoc.model}, {ad_hoc.input_tokens} in, {ad_hoc.output_tokens} out)",
        f"estimated_cost_usd: {ad_hoc.estimated_cost_usd:.8f}",
        "",
        "Monthly design envelope (dev, USD)",
    ]
    for name, band in DESIGN_ENVELOPE_USD:
        lines.append(f"  {name}: {band}")
    lines.append("  target: <= 5.00")
    lines.append("")
    lines.append("If the AWS bill exceeds the target, mitigate in this order:")
    for index, step in enumerate(MITIGATION_ORDER, start=1):
        lines.append(f"  {index}. {step}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="us.amazon.nova-micro-v1:0")
    parser.add_argument("--input-tokens", type=int, default=4000)
    parser.add_argument("--output-tokens", type=int, default=800)
    parser.add_argument("--last-run", type=Path, default=LAST_RUN)
    args = parser.parse_args(argv)
    if args.input_tokens < 0 or args.output_tokens < 0:
        print("token counts must be >= 0", file=sys.stderr)
        return 2
    if not args.last_run.is_file():
        print(f"missing evaluation summary: {args.last_run}", file=sys.stderr)
        return 2
    observed = load_observed(args.last_run)
    print(
        render(
            observed,
            model=args.model,
            input_tokens=args.input_tokens,
            output_tokens=args.output_tokens,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

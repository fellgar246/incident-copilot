"""Register the read-only tool catalog. Refuses search, web search, and unknown tools.

The Gateway resource is applied by this script because the pinned Terraform
provider has no Gateway type. See docs/adrs/ADR-006-agentcore-gateway.md.
Dry-run is the default. GATEWAY_APPLY=1 submits only the catalog below.
"""

from __future__ import annotations

import json
import os
import sys

from agent.register import apply_registration, registration_document


def main() -> int:
    document = registration_document()
    if os.environ.get("GATEWAY_APPLY") == "1":
        import boto3  # type: ignore[import-untyped]

        region = os.environ.get("AWS_REGION", "us-east-1")
        client = boto3.client("bedrock-agentcore-control", region_name=region)
        print(json.dumps(apply_registration(client, document), indent=2))
        return 0
    print(json.dumps(document, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

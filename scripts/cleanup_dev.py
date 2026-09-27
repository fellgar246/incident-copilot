"""Destroy a dev or ephemeral stack. Refuses every other environment name.

Dry-run is the default. Apply requires DESTROY_EPHEMERAL=1 and --confirm destroy-dev.
Local state also requires --allow-local. CI should set TF_STATE_BUCKET instead.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_DIR = REPO_ROOT / "infra" / "environments" / "dev"
INFRA_ROOT = REPO_ROOT / "infra"
CONFIRM = "destroy-dev"
PREVENT_DESTROY = re.compile(r"prevent_destroy\s*=\s*true")


def environment_is_safe(name: str) -> bool:
    return name == "dev" or name.startswith("ephemeral-")


def prevent_destroy_hits(root: Path) -> list[str]:
    hits: list[str] = []
    for path in root.rglob("*.tf"):
        if ".terraform" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if PREVENT_DESTROY.search(text):
            hits.append(str(path.relative_to(root)))
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", default="dev")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--allow-local", action="store_true")
    args = parser.parse_args(argv)

    if not environment_is_safe(args.environment):
        print(
            f"refusing to destroy environment {args.environment!r}",
            file=sys.stderr,
        )
        return 2

    hits = prevent_destroy_hits(INFRA_ROOT)
    if hits:
        print("prevent_destroy is set; destroy is blocked:", file=sys.stderr)
        for hit in hits:
            print(f"  {hit}", file=sys.stderr)
        return 2

    remote_bucket = os.environ.get("TF_STATE_BUCKET", "")
    remote_table = os.environ.get("TF_LOCK_TABLE", "")
    print(f"target environment: {args.environment}")
    print("resources: dev stack in infra/environments/dev")
    print("buckets: force_destroy is set so leftover objects can be removed")
    if not args.apply:
        print("dry-run: terraform destroy was not executed")
        return 0

    if args.confirm != CONFIRM:
        print(f"refusing apply: pass --confirm {CONFIRM}", file=sys.stderr)
        return 2
    if os.environ.get("DESTROY_EPHEMERAL") != "1":
        print("refusing apply: set DESTROY_EPHEMERAL=1", file=sys.stderr)
        return 2
    if remote_bucket == "" and not args.allow_local:
        print(
            "refusing apply: set TF_STATE_BUCKET and TF_LOCK_TABLE, or pass --allow-local",
            file=sys.stderr,
        )
        return 2

    if remote_bucket:
        configured = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "configure_remote_backend.py"),
                "--bucket",
                remote_bucket,
                "--table",
                remote_table,
                "--region",
                os.environ.get("AWS_REGION", "us-east-1"),
            ],
            check=False,
        )
        if configured.returncode != 0:
            return configured.returncode
        init = subprocess.run(
            ["terraform", "init", "-input=false", "-backend-config=backend.hcl"],
            cwd=TERRAFORM_DIR,
            check=False,
        )
        if init.returncode != 0:
            return init.returncode

    destroy = subprocess.run(
        ["terraform", "destroy", "-input=false", "-auto-approve"],
        cwd=TERRAFORM_DIR,
        check=False,
    )
    return destroy.returncode


if __name__ == "__main__":
    raise SystemExit(main())

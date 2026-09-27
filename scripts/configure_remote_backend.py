"""Point the dev stack at an S3 backend when remote state variables are set.

The committed backend stays local so a new account can apply before a state
bucket exists. CI rewrites the working copy only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LOCAL_BACKEND = re.compile(r'backend "local" \{[^}]*\}', re.MULTILINE)
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VERSIONS = REPO_ROOT / "infra" / "environments" / "dev" / "versions.tf"


def use_s3_backend(text: str) -> str:
    """Replace the local backend block with an empty S3 backend."""
    if 'backend "s3"' in text:
        return text
    replaced, count = LOCAL_BACKEND.subn('backend "s3" {}', text, count=1)
    if count != 1:
        raise ValueError("local backend block not found")
    return replaced


def backend_hcl(*, bucket: str, table: str, region: str, key: str) -> str:
    return "\n".join(
        [
            f'bucket         = "{bucket}"',
            f'key            = "{key}"',
            f'region         = "{region}"',
            f'dynamodb_table = "{table}"',
            "encrypt        = true",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", type=Path, default=DEFAULT_VERSIONS)
    parser.add_argument("--bucket", default="")
    parser.add_argument("--table", default="")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--key", default="dev/terraform.tfstate")
    parser.add_argument("--write-hcl", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.bucket == "" and args.table == "":
        print("local backend unchanged")
        return 0
    if args.bucket == "" or args.table == "":
        print("bucket and table are both required for a remote backend", file=sys.stderr)
        return 2
    text = args.versions.read_text(encoding="utf-8")
    try:
        updated = use_s3_backend(text)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    args.versions.write_text(updated, encoding="utf-8")
    hcl_path = args.write_hcl or args.versions.parent / "backend.hcl"
    hcl_path.write_text(
        backend_hcl(bucket=args.bucket, table=args.table, region=args.region, key=args.key),
        encoding="utf-8",
    )
    print(f"remote backend configured: {hcl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

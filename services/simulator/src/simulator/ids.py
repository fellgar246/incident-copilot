"""Stable identifiers derived from a seed so fixtures stay reproducible."""

from __future__ import annotations

import hashlib


def seeded_id(prefix: str, seed: str, name: str, length: int = 16) -> str:
    digest = hashlib.sha256(f"{seed}:{name}".encode()).hexdigest()[:length]
    return f"{prefix}_{digest}"

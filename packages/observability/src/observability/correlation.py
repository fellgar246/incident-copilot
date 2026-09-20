"""Generate correlation identifiers without depending on AWS X-Ray."""

from __future__ import annotations

import uuid


def new_correlation_id() -> str:
    """Return a lowercase UUID4 string suitable for request tracing."""
    return str(uuid.uuid4())

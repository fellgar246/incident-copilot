"""Lambda entrypoint wrapping the FastAPI application."""

from __future__ import annotations

from mangum import Mangum

from api.main import app

handler = Mangum(app, lifespan="off")

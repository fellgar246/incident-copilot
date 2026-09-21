"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from observability.logging import configure_json_logging

from api.deps import AppContainer, build_container
from api.middleware import CorrelationMiddleware
from api.routes.health import router as health_router
from api.routes.incidents import router as incidents_router
from api.routes.stubs import router as stubs_router
from api.settings import Settings


def create_app(
    *,
    container: AppContainer | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    configure_json_logging()
    resolved = container or build_container(settings=settings)
    app = FastAPI(
        title="AI Incident Copilot API",
        version="0.1.0",
        description=(
            "Read-oriented incident API. POST /incidents/simulate returns 201 on create "
            "and 200 when the same Idempotency-Key or simulation_id is replayed."
        ),
    )
    app.state.container = resolved
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(incidents_router)
    app.include_router(stubs_router)
    return app


app = create_app()

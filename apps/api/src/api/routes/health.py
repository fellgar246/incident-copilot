"""Liveness and DynamoDB reachability probes."""

from __future__ import annotations

import logging

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict

from api.deps import get_container

logger = logging.getLogger("api.health")

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class AwsHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    repository: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/aws",
    response_model=AwsHealthResponse,
    responses={503: {"model": AwsHealthResponse}},
)
def health_aws(request: Request, response: Response) -> AwsHealthResponse:
    store = get_container(request).store
    try:
        result = store.ping()
    except (ClientError, BotoCoreError):
        logger.warning("dynamodb_unreachable")
        response.status_code = 503
        return AwsHealthResponse(status="unavailable", repository="dynamodb")
    return AwsHealthResponse(
        status=result.get("status", "ok"),
        repository=result.get("repository", "unknown"),
    )

"""Application dependencies. Unit tests inject in-memory stores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import boto3  # type: ignore[import-untyped]
from cost_guardrails.envfile import parse_env_file
from cost_guardrails.quotas import AppQuotas, load_quotas
from fastapi import Request
from incident_contracts.models import Deployment, Incident
from incident_contracts.repository import IncidentRepository, InMemoryIncidentRepository
from incident_contracts.service import IncidentService

from api.persistence.deployments import InMemoryDeploymentRepository
from api.persistence.dynamodb import DynamoIncidentRepository
from api.settings import Settings, get_settings


class IncidentStore(IncidentRepository, Protocol):
    def ping(self) -> dict[str, str]: ...

    def get_by_idempotency_key(self, key: str) -> Incident | None: ...

    def remember_idempotency(self, key: str, incident_id: str) -> None: ...


class DeploymentStore(Protocol):
    def save_many(self, deployments: list[Deployment]) -> None: ...


@dataclass
class AppContainer:
    settings: Settings
    store: IncidentStore
    deployments: DeploymentStore
    quotas: AppQuotas

    @property
    def service(self) -> IncidentService:
        return IncidentService(self.store)


def load_app_quotas() -> AppQuotas:
    try:
        return load_quotas()
    except KeyError:
        from pathlib import Path

        example = Path(__file__).resolve().parents[4] / ".env.example"
        return load_quotas(parse_env_file(example))


def build_container(
    *,
    settings: Settings | None = None,
    store: IncidentStore | None = None,
    deployments: DeploymentStore | None = None,
    quotas: AppQuotas | None = None,
) -> AppContainer:
    resolved_settings = settings or get_settings()
    resolved_store = store if store is not None else _default_store(resolved_settings)
    if deployments is not None:
        resolved_deployments = deployments
    elif isinstance(resolved_store, DynamoIncidentRepository):
        resolved_deployments = resolved_store
    else:
        resolved_deployments = InMemoryDeploymentRepository()
    return AppContainer(
        settings=resolved_settings,
        store=resolved_store,
        deployments=resolved_deployments,
        quotas=quotas or load_app_quotas(),
    )


def _default_store(settings: Settings) -> IncidentStore:
    if not settings.use_dynamodb:
        return InMemoryIncidentRepository()
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    return DynamoIncidentRepository(
        dynamodb.Table(settings.incidents_table_name),
        dynamodb.Table(settings.deployments_table_name),
        retention_days=settings.log_retention_days,
    )


def get_container(request: Request) -> AppContainer:
    container = request.app.state.container
    if not isinstance(container, AppContainer):
        raise RuntimeError("application container is not configured")
    return container


def get_store(request: Request) -> IncidentStore:
    return get_container(request).store


def get_service(request: Request) -> IncidentService:
    return get_container(request).service

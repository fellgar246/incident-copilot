from __future__ import annotations

from pathlib import Path

import pytest
from api.deps import build_container
from api.main import create_app
from api.persistence.deployments import InMemoryDeploymentRepository
from api.settings import Settings, reset_settings_cache
from cost_guardrails.envfile import parse_env_file
from cost_guardrails.quotas import load_quotas
from fastapi.testclient import TestClient
from incident_contracts.repository import InMemoryIncidentRepository

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = parse_env_file(REPO_ROOT / ".env.example")


@pytest.fixture(autouse=True)
def _quota_env(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_settings_cache()
    for key, value in ENV_EXAMPLE.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("INCIDENT_REPOSITORY", "memory")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        repository="memory",
        incidents_table_name="ai-incident-copilot-dev-incidents",
        deployments_table_name="ai-incident-copilot-dev-deployments",
        aws_region="us-east-1",
        log_retention_days=7,
        cors_origins=("http://localhost:3000",),
    )


@pytest.fixture
def repository() -> InMemoryIncidentRepository:
    return InMemoryIncidentRepository()


@pytest.fixture
def deployments() -> InMemoryDeploymentRepository:
    return InMemoryDeploymentRepository()


@pytest.fixture
def client(
    settings: Settings,
    repository: InMemoryIncidentRepository,
    deployments: InMemoryDeploymentRepository,
) -> TestClient:
    container = build_container(
        settings=settings,
        store=repository,
        deployments=deployments,
        quotas=load_quotas(ENV_EXAMPLE),
    )
    return TestClient(create_app(container=container))

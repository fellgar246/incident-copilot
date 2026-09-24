"""In-memory deployment store used when DynamoDB is not configured."""

from __future__ import annotations

from datetime import datetime

from incident_contracts.models import Deployment


class InMemoryDeploymentRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str], Deployment] = {}

    def save_many(self, deployments: list[Deployment]) -> None:
        for item in deployments:
            key = (item.service, item.version, item.deployed_at.isoformat())
            self._items[key] = item.model_copy(deep=True)

    def list_for_service(self, service: str) -> list[Deployment]:
        found = [
            item.model_copy(deep=True) for item in self._items.values() if item.service == service
        ]
        return sorted(found, key=lambda item: item.deployed_at, reverse=True)

    def query(self, *, service: str, since: datetime, limit: int) -> list[Deployment]:
        matched = [item for item in self.list_for_service(service) if item.deployed_at >= since]
        return matched[:limit]

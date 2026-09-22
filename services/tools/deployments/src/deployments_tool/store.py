"""In-memory and DynamoDB readers for recent demo deployments."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from incident_contracts.keys import deployment_pk, deployment_sk, utc_sort_timestamp
from incident_contracts.models import Deployment
from incident_contracts.surface import DEMO_SERVICES

from deployments_tool.errors import AllowlistError, ToolError, TransientToolError

_THROTTLE_CODES = frozenset(
    {
        "ThrottlingException",
        "Throttling",
        "TooManyRequestsException",
        "RequestLimitExceeded",
        "ProvisionedThroughputExceededException",
    }
)
_PAGE_LIMIT = 3


def require_service(service: str) -> str:
    """Return `service` when it is one of the demo services."""
    if service not in DEMO_SERVICES:
        raise AllowlistError(f"service is not allowlisted: {service}")
    return service


def as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return moment.astimezone(UTC)


class MemoryDeploymentStore:
    """Idempotent deployment store keyed by service, version, and time."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str], Deployment] = {}

    def write_deployment(self, deployment: Deployment) -> None:
        require_service(deployment.service)
        key = (deployment.service, deployment.version, as_utc(deployment.deployed_at).isoformat())
        self._items[key] = deployment.model_copy(deep=True)

    def query(self, *, service: str, since: datetime, limit: int) -> list[Deployment]:
        require_service(service)
        window_start = as_utc(since)
        matched = [
            item.model_copy(deep=True)
            for item in self._items.values()
            if item.service == service and as_utc(item.deployed_at) >= window_start
        ]
        matched.sort(key=lambda item: item.deployed_at, reverse=True)
        return matched[:limit]


class DynamoDeploymentStore:
    """Read deployment items written with the shared pk/sk contract."""

    def __init__(self, table: Any) -> None:
        self._table = table

    def write_deployment(self, deployment: Deployment) -> None:
        require_service(deployment.service)
        item = {
            "pk": deployment_pk(deployment.service),
            "sk": deployment_sk(deployment.deployed_at, deployment.version),
            "entity_type": "DEPLOYMENT",
            "service": deployment.service,
            "document": deployment.model_dump_json(),
        }
        self._call(lambda: self._table.put_item(Item=item))

    def query(self, *, service: str, since: datetime, limit: int) -> list[Deployment]:
        require_service(service)
        found: list[Deployment] = []
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": "pk = :pk AND sk >= :since",
            "ExpressionAttributeValues": {
                ":pk": deployment_pk(service),
                ":since": f"DEPLOY#{utc_sort_timestamp(as_utc(since))}",
            },
            "ScanIndexForward": False,
            "Limit": limit,
            "ConsistentRead": True,
        }
        for _ in range(_PAGE_LIMIT):
            response = self._call(lambda: self._table.query(**kwargs))
            for item in response.get("Items", []):
                if not isinstance(item, dict) or "document" not in item:
                    continue
                found.append(Deployment.model_validate_json(str(item["document"])))
                if len(found) >= limit:
                    return found
            token = response.get("LastEvaluatedKey")
            if not token:
                break
            kwargs["ExclusiveStartKey"] = token
        return found

    def _call(self, fn: Any) -> Any:
        try:
            return fn()
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in _THROTTLE_CODES:
                raise TransientToolError(code) from exc
            raise ToolError(code or "dynamodb request failed") from exc

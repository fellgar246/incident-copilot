"""Repository factory. DynamoDB adapter is shared with the API process."""

from __future__ import annotations

from incident_contracts.repository import IncidentRepository, InMemoryIncidentRepository

from incident_worker.settings import Settings, get_settings


def build_repository(settings: Settings | None = None) -> IncidentRepository:
    resolved = settings or get_settings()
    if not resolved.use_dynamodb:
        return InMemoryIncidentRepository()
    import boto3  # type: ignore[import-untyped]
    from api.persistence.dynamodb import DynamoIncidentRepository

    dynamodb = boto3.resource("dynamodb", region_name=resolved.aws_region)
    return DynamoIncidentRepository(
        dynamodb.Table(resolved.incidents_table_name),
        dynamodb.Table(resolved.deployments_table_name),
        retention_days=resolved.log_retention_days,
    )

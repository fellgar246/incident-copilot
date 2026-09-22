"""DynamoDB adapter for incidents, append-only events, and deployments."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from boto3.dynamodb.conditions import Attr, Key  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from incident_contracts.enums import IncidentStatus
from incident_contracts.keys import (
    EVENT_SK_PREFIX,
    INDEX_SK,
    METADATA_SK,
    deployment_pk,
    event_id_pk,
    idempotency_pk,
    incident_pk,
    simulation_pk,
    source_event_pk,
)
from incident_contracts.models import Deployment, Incident, IncidentEvent

from api.persistence.mapping import (
    ATTR_DOCUMENT,
    ATTR_PK,
    ATTR_SK,
    ENTITY_INCIDENT,
    deployment_from_item,
    deployment_item,
    event_from_item,
    event_id_index_item,
    event_item,
    idempotency_index_item,
    incident_from_item,
    incident_item,
    matches_filters,
    simulation_index_item,
    source_index_item,
    ttl_epoch,
)

CONDITION_NEW_ITEM = f"attribute_not_exists({ATTR_PK}) AND attribute_not_exists({ATTR_SK})"


class DynamoIncidentRepository:
    """Incident store backed by DynamoDB. Event items are never updated in place."""

    def __init__(
        self,
        table: Any,
        deployments_table: Any,
        *,
        retention_days: int,
        client: Any | None = None,
    ) -> None:
        self._table = table
        self._deployments = deployments_table
        self._retention_days = retention_days
        self._client = client if client is not None else table.meta.client

    def _expires_at(self, moment: datetime | None = None) -> int:
        return ttl_epoch(moment or datetime.now(UTC), self._retention_days)

    def ping(self) -> dict[str, str]:
        self._client.describe_table(TableName=self._table.name)
        self._client.describe_table(TableName=self._deployments.name)
        return {"status": "ok", "repository": "dynamodb"}

    def get(self, incident_id: str) -> Incident | None:
        response = self._table.get_item(
            Key={ATTR_PK: incident_pk(incident_id), ATTR_SK: METADATA_SK},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if item is None or ATTR_DOCUMENT not in item:
            return None
        return incident_from_item(item)

    def _get_by_index(self, pk: str) -> Incident | None:
        response = self._table.get_item(
            Key={ATTR_PK: pk, ATTR_SK: INDEX_SK},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if item is None:
            return None
        incident_id = item.get("incident_id")
        if not isinstance(incident_id, str):
            return None
        return self.get(incident_id)

    def get_by_source_event_id(self, event_id: str) -> Incident | None:
        return self._get_by_index(source_event_pk(event_id))

    def get_by_simulation_id(self, simulation_id: str) -> Incident | None:
        return self._get_by_index(simulation_pk(simulation_id))

    def get_by_event_id(self, event_id: str) -> Incident | None:
        return self._get_by_index(event_id_pk(event_id))

    def get_by_idempotency_key(self, key: str) -> Incident | None:
        return self._get_by_index(idempotency_pk(key))

    def remember_idempotency(self, key: str, incident_id: str) -> None:
        try:
            self._table.put_item(
                Item=idempotency_index_item(key, incident_id, expires_at=self._expires_at()),
                ConditionExpression=CONDITION_NEW_ITEM,
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise

    def save(self, incident: Incident) -> None:
        expires_at = self._expires_at(incident.updated_at)
        self._table.put_item(Item=incident_item(incident, expires_at=expires_at))
        if incident.source_event_id:
            self._put_index_if_absent(
                source_index_item(
                    incident.source_event_id, incident.incident_id, expires_at=expires_at
                )
            )
        if incident.simulation_id:
            self._put_index_if_absent(
                simulation_index_item(
                    incident.simulation_id, incident.incident_id, expires_at=expires_at
                )
            )

    def _put_index_if_absent(self, item: dict[str, Any]) -> None:
        try:
            self._table.put_item(Item=item, ConditionExpression=CONDITION_NEW_ITEM)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise

    def append_event(self, event: IncidentEvent) -> None:
        if self.event_exists(event.event_id):
            return
        expires_at = self._expires_at(event.timestamp)
        try:
            self._table.put_item(
                Item=event_id_index_item(event.event_id, event.incident_id, expires_at=expires_at),
                ConditionExpression=CONDITION_NEW_ITEM,
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return
            raise
        try:
            self._table.put_item(
                Item=event_item(event, expires_at=expires_at),
                ConditionExpression=CONDITION_NEW_ITEM,
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return
            raise

    def event_exists(self, event_id: str) -> bool:
        response = self._table.get_item(
            Key={ATTR_PK: event_id_pk(event_id), ATTR_SK: INDEX_SK},
            ConsistentRead=True,
        )
        return "Item" in response

    def list_events(self, incident_id: str) -> list[IncidentEvent]:
        events: list[IncidentEvent] = []
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": Key("pk").eq(incident_pk(incident_id))
            & Key("sk").begins_with(EVENT_SK_PREFIX),
            "ConsistentRead": True,
        }
        while True:
            response = self._table.query(**kwargs)
            for item in response.get("Items", []):
                events.append(event_from_item(item))
            start = response.get("LastEvaluatedKey")
            if not start:
                break
            kwargs["ExclusiveStartKey"] = start
        return events

    def list_incidents(
        self,
        *,
        status: IncidentStatus | None = None,
        service: str | None = None,
    ) -> list[Incident]:
        incidents: list[Incident] = []
        kwargs: dict[str, Any] = {
            "FilterExpression": Attr("entity_type").eq(ENTITY_INCIDENT),
            "ConsistentRead": True,
        }
        while True:
            response = self._table.scan(**kwargs)
            for item in response.get("Items", []):
                if matches_filters(item, status=status, service=service):
                    incidents.append(incident_from_item(item))
            start = response.get("LastEvaluatedKey")
            if not start:
                break
            kwargs["ExclusiveStartKey"] = start
        return sorted(incidents, key=lambda item: item.started_at, reverse=True)

    def save_many(self, deployments: list[Deployment]) -> None:
        now = datetime.now(UTC)
        for deployment in deployments:
            self._deployments.put_item(
                Item=deployment_item(deployment, expires_at=self._expires_at(now))
            )

    def list_deployments(self, service: str) -> list[Deployment]:
        items: list[Deployment] = []
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": Key("pk").eq(deployment_pk(service)),
            "ConsistentRead": True,
        }
        while True:
            response = self._deployments.query(**kwargs)
            for item in response.get("Items", []):
                items.append(deployment_from_item(item))
            start = response.get("LastEvaluatedKey")
            if not start:
                break
            kwargs["ExclusiveStartKey"] = start
        return sorted(items, key=lambda item: item.deployed_at, reverse=True)

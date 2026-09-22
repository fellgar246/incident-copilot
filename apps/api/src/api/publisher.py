"""Optional EventBridge fan-out for incident.detected.v1."""

from __future__ import annotations

import json
import logging
from typing import Protocol

from incident_contracts.events import (
    DEFAULT_EVENT_SOURCE,
    INCIDENT_DETECTED_DETAIL_TYPE,
    IncidentDetectedV1,
)

logger = logging.getLogger("api.events")


class EventPublisher(Protocol):
    def publish_detected(self, event: IncidentDetectedV1) -> None: ...


class NullEventPublisher:
    """No-op publisher used when EVENT_BUS_NAME is unset (local tests)."""

    def publish_detected(self, event: IncidentDetectedV1) -> None:
        return


class EventBridgePublisher:
    def __init__(self, client: object, *, bus_name: str, source: str) -> None:
        self._client = client
        self._bus_name = bus_name
        self._source = source or DEFAULT_EVENT_SOURCE

    def publish_detected(self, event: IncidentDetectedV1) -> None:
        detail = event.model_dump(mode="json", exclude_none=True)
        self._client.put_events(  # type: ignore[attr-defined]
            Entries=[
                {
                    "Source": self._source,
                    "DetailType": INCIDENT_DETECTED_DETAIL_TYPE,
                    "Detail": json.dumps(detail),
                    "EventBusName": self._bus_name,
                }
            ]
        )
        logger.info(
            "incident.bus_published",
            extra={
                "fields": {
                    "event_id": event.event_id,
                    "correlation_id": event.correlation_id,
                    "bus": self._bus_name,
                }
            },
        )

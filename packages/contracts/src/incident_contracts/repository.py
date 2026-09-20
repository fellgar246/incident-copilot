"""Incident persistence port and an in-memory implementation for local tests."""

from __future__ import annotations

from typing import Protocol

from incident_contracts.enums import IncidentStatus
from incident_contracts.models import Incident, IncidentEvent


class IncidentRepository(Protocol):
    def get(self, incident_id: str) -> Incident | None: ...

    def get_by_source_event_id(self, event_id: str) -> Incident | None: ...

    def get_by_simulation_id(self, simulation_id: str) -> Incident | None: ...

    def get_by_event_id(self, event_id: str) -> Incident | None: ...

    def save(self, incident: Incident) -> None: ...

    def append_event(self, event: IncidentEvent) -> None: ...

    def list_events(self, incident_id: str) -> list[IncidentEvent]: ...

    def list_incidents(self) -> list[Incident]: ...

    def event_exists(self, event_id: str) -> bool: ...


class InMemoryIncidentRepository:
    """Append-only events; incidents are replaced as a whole, never mutated in place."""

    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}
        self._events: dict[str, list[IncidentEvent]] = {}
        self._appended_event_ids: dict[str, str] = {}
        self._source_event_index: dict[str, str] = {}
        self._simulation_index: dict[str, str] = {}

    def get(self, incident_id: str) -> Incident | None:
        incident = self._incidents.get(incident_id)
        return incident.model_copy(deep=True) if incident else None

    def get_by_source_event_id(self, event_id: str) -> Incident | None:
        incident_id = self._source_event_index.get(event_id)
        if incident_id is None:
            return None
        return self.get(incident_id)

    def get_by_simulation_id(self, simulation_id: str) -> Incident | None:
        incident_id = self._simulation_index.get(simulation_id)
        if incident_id is None:
            return None
        return self.get(incident_id)

    def get_by_event_id(self, event_id: str) -> Incident | None:
        incident_id = self._appended_event_ids.get(event_id)
        if incident_id is None:
            return None
        return self.get(incident_id)

    def save(self, incident: Incident) -> None:
        stored = incident.model_copy(deep=True)
        self._incidents[stored.incident_id] = stored
        if stored.source_event_id:
            self._source_event_index[stored.source_event_id] = stored.incident_id
        if stored.simulation_id:
            self._simulation_index[stored.simulation_id] = stored.incident_id

    def append_event(self, event: IncidentEvent) -> None:
        if event.event_id in self._appended_event_ids:
            return
        bucket = self._events.setdefault(event.incident_id, [])
        bucket.append(event)
        self._appended_event_ids[event.event_id] = event.incident_id

    def list_events(self, incident_id: str) -> list[IncidentEvent]:
        events = list(self._events.get(incident_id, []))
        return sorted(events, key=lambda item: item.timestamp)

    def list_incidents(self) -> list[Incident]:
        incidents = [item.model_copy(deep=True) for item in self._incidents.values()]
        return sorted(incidents, key=lambda item: item.started_at, reverse=True)

    def event_exists(self, event_id: str) -> bool:
        return event_id in self._appended_event_ids

    def has_active_remediation(self, incident_id: str) -> bool:
        incident = self._incidents.get(incident_id)
        if incident is None or incident.active_remediation_id is None:
            return False
        return incident.status == IncidentStatus.REMEDIATING

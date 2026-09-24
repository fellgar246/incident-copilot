"""Persisted record of one investigation, including token and cost counters."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class AgentRunStatus(StrEnum):
    QUEUED = "QUEUED"
    INVESTIGATING = "INVESTIGATING"
    DIAGNOSED = "DIAGNOSED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class AgentRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_run_id: str
    incident_id: str
    correlation_id: str
    status: AgentRunStatus
    model: str
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    rag_calls: int = 0
    runtime_ms: int = 0
    estimated_cost_usd: float = 0.0
    stop_reason: str | None = None
    idempotency_key: str | None = None
    created_at: datetime
    updated_at: datetime
    tool_names: list[str] = Field(default_factory=list)


class AgentRunStore(Protocol):
    def save(self, record: AgentRunRecord) -> None: ...

    def get(self, agent_run_id: str) -> AgentRunRecord | None: ...

    def list_for_incident(self, incident_id: str) -> list[AgentRunRecord]: ...

    def get_by_idempotency(self, incident_id: str, key: str) -> AgentRunRecord | None: ...


class InMemoryAgentRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, AgentRunRecord] = {}

    def save(self, record: AgentRunRecord) -> None:
        self._runs[record.agent_run_id] = record.model_copy(deep=True)

    def get(self, agent_run_id: str) -> AgentRunRecord | None:
        found = self._runs.get(agent_run_id)
        return found.model_copy(deep=True) if found else None

    def list_for_incident(self, incident_id: str) -> list[AgentRunRecord]:
        rows = [
            item.model_copy(deep=True)
            for item in self._runs.values()
            if item.incident_id == incident_id
        ]
        return sorted(rows, key=lambda item: item.created_at)

    def get_by_idempotency(self, incident_id: str, key: str) -> AgentRunRecord | None:
        for item in self._runs.values():
            if item.incident_id == incident_id and item.idempotency_key == key:
                return item.model_copy(deep=True)
        return None

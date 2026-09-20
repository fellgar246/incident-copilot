"""Every agent execution is scoped to an incident and a correlation id."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AgentRunContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    incident_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    agent_run_id: str = Field(min_length=1)

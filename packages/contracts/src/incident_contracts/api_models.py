"""HTTP request bodies for the product API. Handlers land in a later slice."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from incident_contracts.enums import ScenarioId


class SimulateIncidentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: ScenarioId
    seed: str | None = None


class ApproveIncidentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str = Field(min_length=1)


class RejectIncidentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str = Field(min_length=1)
    reason: str | None = None


class RemediateIncidentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str = Field(min_length=1)

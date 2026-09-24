"""Parse a model diagnosis into the shared Diagnosis contract."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from incident_contracts.enums import EvidenceKind
from incident_contracts.models import Diagnosis, Evidence
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class DiagnosisParseError(ValueError):
    """The model text was not a valid diagnosis object."""


class _EvidenceDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    evidence_id: str = ""
    kind: EvidenceKind = EvidenceKind.OBSERVED
    source: str = "agent"
    summary: str
    observed_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class _DiagnosisDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str
    probable_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[_EvidenceDraft] = Field(default_factory=list)
    retrieved_sources: list[str] = Field(default_factory=list)
    alternative_hypotheses: list[str] = Field(default_factory=list)
    recommended_action: str
    requires_approval: bool = True


def extract_json_object(text: str) -> dict[str, Any]:
    """Return the first JSON object in `text`."""
    fenced = _FENCE.search(text)
    raw = fenced.group(1) if fenced else None
    if raw is None:
        found = _OBJECT.search(text)
        if found is None:
            raise DiagnosisParseError("model output did not contain a JSON object")
        raw = found.group(0)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiagnosisParseError("model output was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise DiagnosisParseError("model output JSON was not an object")
    return parsed


def parse_diagnosis(text: str, *, observed_at: datetime, id_prefix: str) -> Diagnosis:
    """Validate model JSON and fill evidence identifiers the model omitted."""
    try:
        draft = _DiagnosisDraft.model_validate(extract_json_object(text))
    except ValidationError as exc:
        raise DiagnosisParseError("diagnosis failed validation") from exc
    evidence: list[Evidence] = []
    for index, item in enumerate(draft.evidence, start=1):
        evidence.append(
            Evidence(
                evidence_id=item.evidence_id or f"{id_prefix}_evd_{index}",
                kind=item.kind,
                source=item.source,
                summary=item.summary,
                observed_at=item.observed_at or observed_at,
                payload=item.payload,
            )
        )
    destructive = "delete_resource" in draft.recommended_action.lower()
    return Diagnosis(
        summary=draft.summary,
        probable_cause=draft.probable_cause,
        confidence=draft.confidence,
        evidence=evidence,
        retrieved_sources=draft.retrieved_sources,
        alternative_hypotheses=draft.alternative_hypotheses,
        recommended_action=draft.recommended_action,
        requires_approval=draft.requires_approval,
        destructive=destructive,
    )

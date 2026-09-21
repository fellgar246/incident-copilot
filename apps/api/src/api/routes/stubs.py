"""Placeholder mutating routes that are not implemented in this HTTP slice."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _not_implemented() -> None:
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.post("/incidents/{id}/investigate", status_code=501)
def investigate_incident(id: str) -> None:
    _not_implemented()


@router.post("/incidents/{id}/approve", status_code=501)
def approve_incident(id: str) -> None:
    _not_implemented()


@router.post("/incidents/{id}/reject", status_code=501)
def reject_incident(id: str) -> None:
    _not_implemented()


@router.post("/incidents/{id}/remediate", status_code=501)
def remediate_incident(id: str) -> None:
    _not_implemented()


@router.get("/incidents/{id}/agent-runs", status_code=501)
def list_agent_runs(id: str) -> None:
    _not_implemented()


@router.get("/metrics/costs", status_code=501)
def metrics_costs() -> None:
    _not_implemented()


@router.get("/evaluations", status_code=501)
def list_evaluations() -> None:
    _not_implemented()

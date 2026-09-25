"""Placeholder mutating routes that are not implemented in this HTTP slice."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _not_implemented() -> None:
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.get("/evaluations", status_code=501)
def list_evaluations() -> None:
    _not_implemented()

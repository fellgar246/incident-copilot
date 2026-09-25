"""Request and result models for search_runbooks."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    service: str
    top_k: int = Field(ge=1, le=4)


class HitMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    document_type: str
    severity: str = ""
    version: str = ""
    updated_at: str = ""


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    score: float = Field(ge=0)
    snippet: str
    metadata: HitMetadata


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str = "search_runbooks"
    tool_class: str = "READ_ONLY"
    requires_approval: bool = False
    query: str
    service: str
    top_k: int
    redacted: bool = True
    truncated: bool = False
    untrusted: bool = True
    hits: list[SearchHit]

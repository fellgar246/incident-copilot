"""Rank corpus documents for one service. Retrieved text stays untrusted data."""

from __future__ import annotations

import re
from dataclasses import dataclass

from knowledge_tool.corpus import Document

_TOKEN = re.compile(r"[a-z0-9]+")
_SNIPPET_CHARS = 400


@dataclass(frozen=True, slots=True)
class Hit:
    document_id: str
    score: float
    snippet: str
    metadata: dict[str, str]


def search_documents(
    documents: tuple[Document, ...] | list[Document],
    *,
    query: str,
    service: str,
    top_k: int,
) -> list[Hit]:
    """Return the closest documents for `service`. Instructions in the body are not followed."""
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    needles = _tokens(query)
    if not needles:
        return []
    ranked: list[tuple[float, str, Document]] = []
    for document in documents:
        if document.service != service:
            continue
        haystack = _tokens(f"{document.document_id} {document.body}")
        if not haystack:
            continue
        overlap = len(needles & haystack)
        if overlap == 0:
            continue
        score = overlap / len(needles)
        if document.document_type == "runbook":
            score += 0.15
        ranked.append((score, document.document_id, document))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    hits: list[Hit] = []
    for score, _document_id, document in ranked[:top_k]:
        hits.append(
            Hit(
                document_id=document.document_id,
                score=round(min(score, 1.0), 4),
                snippet=_snippet(document.body),
                metadata=document.metadata,
            )
        )
    return hits


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _snippet(body: str) -> str:
    flat = " ".join(body.split())
    if len(flat) <= _SNIPPET_CHARS:
        return flat
    return flat[: _SNIPPET_CHARS - 1].rstrip() + "…"

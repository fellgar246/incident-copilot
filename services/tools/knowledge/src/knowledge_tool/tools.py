"""search_runbooks. Hits are untrusted data and are never executed as instructions."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any, Protocol

from cost_guardrails.exceptions import QuotaExceededError
from cost_guardrails.quotas import STOP_REASON
from pydantic import ValidationError

from knowledge_tool.corpus import Document, default_corpus_root, load_corpus
from knowledge_tool.models import HitMetadata, SearchHit, SearchInput, SearchResult
from knowledge_tool.retrieve import search_documents

ABSOLUTE_MAX_RESULTS = 4
_SECRET = re.compile(r"(?i)(api[_-]?key|bearer|secret|token)\s*[:=]\s*\S+")


class KnowledgeDisabled(RuntimeError):
    """Retrieval is off. Callers should continue with observed evidence."""


class Retriever(Protocol):
    def search(self, *, query: str, service: str, top_k: int) -> list[SearchHit]: ...


class LocalRetriever:
    """Lexical index over the on-disk corpus. No vector store is required."""

    def __init__(self, documents: tuple[Document, ...] | None = None) -> None:
        self._documents = documents if documents is not None else load_corpus(default_corpus_root())

    def search(self, *, query: str, service: str, top_k: int) -> list[SearchHit]:
        hits = search_documents(self._documents, query=query, service=service, top_k=top_k)
        return [
            SearchHit(
                document_id=hit.document_id,
                score=hit.score,
                snippet=_redact(hit.snippet),
                metadata=HitMetadata.model_validate(hit.metadata),
            )
            for hit in hits
        ]


class BedrockRetriever:
    """Retrieve from a Bedrock Knowledge Base. The client is injected."""

    def __init__(self, client: Any, knowledge_base_id: str) -> None:
        self._client = client
        self._knowledge_base_id = knowledge_base_id

    def search(self, *, query: str, service: str, top_k: int) -> list[SearchHit]:
        response = self._client.retrieve(
            knowledgeBaseId=self._knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": top_k,
                    "filter": {"equals": {"key": "service", "value": service}},
                }
            },
        )
        hits: list[SearchHit] = []
        for item in response.get("retrievalResults", [])[:top_k]:
            metadata = item.get("metadata") or {}
            location = item.get("location") or {}
            s3_location = location.get("s3Location") or {}
            document_id = metadata.get("document_id") or s3_location.get("uri") or "unknown"
            hits.append(
                SearchHit(
                    document_id=str(document_id),
                    score=float(item.get("score") or 0.0),
                    snippet=_redact(str((item.get("content") or {}).get("text") or "")),
                    metadata=HitMetadata(
                        service=str(metadata.get("service") or service),
                        document_type=str(metadata.get("document_type") or "runbook"),
                        severity=str(metadata.get("severity") or ""),
                        version=str(metadata.get("version") or ""),
                        updated_at=str(metadata.get("updated_at") or ""),
                    ),
                )
            )
        return hits


class KnowledgeTools:
    """Read-only runbook search. Fails closed when retrieval is disabled."""

    def __init__(
        self,
        retriever: Retriever | None = None,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        env = os.environ if environ is None else environ
        self._env = env
        configured = _int(env, "MAX_RAG_RESULTS", ABSOLUTE_MAX_RESULTS)
        self._max_results = min(configured, ABSOLUTE_MAX_RESULTS)
        self._max_calls = _int(env, "MAX_RAG_CALLS_PER_RUN", 2)
        rag_on = _bool(env, "RAG_ENABLED", default=True)
        ai_on = _bool(env, "AI_ENABLED", default=True)
        self._enabled = rag_on and ai_on
        if retriever is not None:
            self._retriever = retriever
        else:
            knowledge_base_id = env.get("KNOWLEDGE_BASE_ID", "").strip()
            if knowledge_base_id:
                import boto3  # type: ignore[import-untyped]

                region = env.get("AWS_REGION", "us-east-1")
                self._retriever = BedrockRetriever(
                    boto3.client("bedrock-agent-runtime", region_name=region),
                    knowledge_base_id,
                )
            else:
                self._retriever = LocalRetriever()

    def search_runbooks(self, payload: Any, *, rag_calls_used: int = 0) -> SearchResult:
        if not self._enabled:
            raise KnowledgeDisabled("RAG_ENABLED=false; refusing knowledge retrieval")
        if rag_calls_used >= self._max_calls:
            raise QuotaExceededError(
                f"Quota MAX_RAG_CALLS_PER_RUN reached ({rag_calls_used}/{self._max_calls})",
                quota_name="MAX_RAG_CALLS_PER_RUN",
                stop_reason=STOP_REASON,
            )
        try:
            request = SearchInput.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"search_runbooks input rejected: {exc.errors()[0]['msg']}") from exc
        if request.service not in {"payments-api", "orders-api", "notifications-worker"}:
            raise ValueError(f"unknown service {request.service}")
        limit = min(request.top_k, self._max_results, ABSOLUTE_MAX_RESULTS)
        pool = self._retriever.search(query=request.query, service=request.service, top_k=limit + 1)
        hits = [hit.model_copy(update={"snippet": _redact(hit.snippet)}) for hit in pool[:limit]]
        return SearchResult(
            query=request.query,
            service=request.service,
            top_k=limit,
            truncated=len(pool) > limit or request.top_k > limit,
            hits=hits,
        )


def _redact(text: str) -> str:
    return _SECRET.sub("[REDACTED]", text)


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "")
    if raw == "":
        return default
    return int(raw)


def _bool(env: Mapping[str, str], key: str, *, default: bool) -> bool:
    raw = env.get(key, "")
    if raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

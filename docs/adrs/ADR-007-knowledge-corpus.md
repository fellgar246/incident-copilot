# ADR-007 — Operational knowledge corpus

- **Status:** accepted
- **Date:** 2026-09-24
- **Deciders:** project owner

## Context

Diagnosis has to keep observed evidence separate from retrieved guidance. The corpus is small on purpose: runbooks, postmortems, service notes, and a few operational decisions, together under 50 MB. Managed Knowledge Base storage is about USD 5 per GB-month, so 50 MB is about USD 0.25 per month of index storage. OpenSearch Serverless is a different price: its minimum capacity would exceed the monthly target. This decision amends the catalog line in ADR-006, which left `search_runbooks` unregistered.

## Decision

1. **Corpus.** Metadata-bearing Markdown under `docs/runbooks`, `docs/postmortems`, `docs/adrs`, and `docs/services` is the corpus. Files without that metadata, including architecture decisions, are not ingested. Each document names `service`, `document_type`, `severity`, `version`, and `updated_at`.
2. **Storage.** Terraform creates a private S3 bucket and `knowledge-tool-role`. The role may `s3:GetObject` and `s3:ListBucket` on that bucket and `bedrock:Retrieve` on knowledge bases in this region. It cannot invoke a model.
3. **Knowledge base.** The pinned AWS provider can describe a Bedrock Knowledge Base only together with a vector collection. This environment does not create that collection. `scripts/sync_knowledge.py` uploads the corpus and, when `KNOWLEDGE_APPLY=1` plus a base id and a data source id are set, starts one ingestion job. It does not create a vector store.
4. **Retrieval path.** With no `KNOWLEDGE_BASE_ID`, `search_runbooks` reads the same corpus through a local index. With a base id, it calls `bedrock:Retrieve` and filters on `service`. `top_k` is capped by `MAX_RAG_RESULTS` and by 4. A run may call the tool at most `MAX_RAG_CALLS_PER_RUN` (2 in dev).
5. **Circuit breaker.** `RAG_ENABLED=false` makes the tool fail closed. The agent continues from observed evidence. The bucket and role stay in place.
6. **Untrusted data.** Hits set `untrusted: true` and return a document id. Text in a hit is not an instruction and cannot add a tool.

## Cost impact

- The bucket is private, encrypted, and tiny. Noncurrent versions expire after 7 days.
- No OpenSearch collection is provisioned, so that minimum charge does not apply.
- Retrieval calls are capped per run. Gateway Search and Web Search stay off.

## Security impact

- The tool role cannot write the bucket or invoke a foundation model.
- Returned snippets are redacted for token-shaped secrets.
- Source ids are copied onto the diagnosis as `retrieved_sources`, separate from observed evidence.

## Review date

Revisit when a vector store fits the monthly target, and fold ingestion into Terraform at that point.

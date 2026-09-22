# ADR-003 — HTTP API and DynamoDB persistence

- **Status:** accepted
- **Date:** 2026-09-20
- **Deciders:** project owner

## Context

Incident state lived only in memory. The dashboard and workers need an HTTP surface and durable, serverless storage. Mutable calls must be safe to retry.

## Decision

1. **Port behind an interface.** `IncidentRepository` stays the domain port. Unit tests use the in-memory adapter. The API process selects DynamoDB when `INCIDENT_REPOSITORY=dynamodb`.
2. **Single item collection for incidents and events.** Incident metadata is `pk=INCIDENT#{id}`, `sk=METADATA`. Timeline rows use `sk=EVENT#{timestamp}#{event_id}` and are written with a create-only condition. Events are never updated in place.
3. **Uniqueness items** (`SOURCE#`, `SIMULATION#`, `EVENTID#`, `IDEM#`) make ingest and simulate idempotent without global secondary indexes.
4. **Separate deployments table** so release metadata can be seeded independently of incident state.
5. **TTL** on `expires_at` matches `LOG_RETENTION_DAYS` (7 in `dev`). Billing mode is on-demand.
6. **Idempotent simulate semantics.** `POST /incidents/simulate` returns **201** when a new incident is created and **200** with the existing representation when `Idempotency-Key` or `simulation_id` is replayed. A second incident is never created. This slice does not use 409 for a matching replay.
7. **Lambda adapter.** FastAPI stays the application; Mangum is the AWS entrypoint. `api-role` may only write logs for its function and read/write the two DynamoDB tables.

## Cost impact

- No always-on compute. Lambda memory is 256 MB with a short timeout and reserved concurrency of 5.
- On-demand DynamoDB plus 7-day TTL keeps stored items small.

## Security impact

- Structured JSON logs carry `request_id`, `incident_id`, and `correlation_id`. Bearer tokens, AWS credentials, and other secret fields are redacted.
- `GET /health/aws` reports DynamoDB reachability without returning error details or secrets.
- IAM for `api-role` is table-ARN scoped; it does not use `Action: *` or `Resource: *`.

## Review date

Revisit if listing volume needs a query index instead of a bounded scan, or when CloudWatch Alarms become a second producer on the event bus.

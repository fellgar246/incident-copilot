# ADR-004 — Event-driven incident ingest

- **Status:** accepted
- **Date:** 2026-09-20
- **Deciders:** project owner

## Context

HTTP `POST /incidents/simulate` can create incidents directly. Production-shaped detection must enter through a bus with retries and a dead-letter queue, using `event_id` as the idempotency key so duplicates never create a second incident.

## Decision

1. **Pipeline.** Custom EventBridge bus → SQS ingest queue → `incident-worker` Lambda → DynamoDB. Failed receives after three attempts land on an SQS DLQ. EventBridge target retries are also capped at three.
2. **Contract.** Producers emit `incident.detected.v1`. The JSON Schema lives in `packages/contracts`. Consumers ignore unknown fields and raise `UnsupportedSchemaVersionError` for a higher `schema_version`.
3. **Worker.** `investigation-worker-role` may write the incidents table and read the ingest queue. Timeout stays short. Structured logs always include `event_id`, `incident_id`, and `correlation_id` when known. AgentCore is not granted in this slice.
4. **HTTP simulate is a test shortcut.** It still writes DynamoDB so local demos return the incident immediately. When `EVENT_BUS_NAME` is set it also publishes to the bus; the worker is idempotent on `event_id`. The EventBridge path is the integration path (`scripts/trigger_incident.py` and the worker).
5. **Observability.** CloudWatch alarm `{project}-{environment}-dlq_messages` watches DLQ depth (`ApproximateNumberOfMessagesVisible`).

## Cost impact

- No always-on compute. Worker memory is 256 MB, timeout 10 s, reserved concurrency 2.
- SQS and EventBridge are pay-per-request. DLQ retention is 14 days.

## Security impact

- Worker IAM is table-ARN and queue-ARN scoped. It cannot invoke the agent.
- Poison payloads fail the record, retry a bounded number of times, then become visible on the DLQ alarm.

## Review date

Revisit when CloudWatch Alarms publish onto the same bus, or when the worker starts the investigation loop.

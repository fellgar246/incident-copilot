# Demo services

Synthetic services used by the local simulator and, later, by telemetry and runbooks. They are not production workloads.

## payments-api

HTTP API. Primary demo service.

Typical signal: elevated 5xx and p95 latency after a release (`deployment_regression`). Brief CPU spikes are used for the false-positive case.

## orders-api

HTTP API.

Typical signal: high latency with `POOL_EXHAUSTED` errors and a custom connection-count metric near its limit.

## notifications-worker

Queue consumer.

Typical signal: growing visible messages, rising age-of-oldest-message, and long worker duration.

## Telemetry

Each service writes structured JSON logs to one allowlisted group:

- `/ai-incident-copilot/dev/payments-api`
- `/ai-incident-copilot/dev/orders-api`
- `/ai-incident-copilot/dev/notifications-worker`

Custom metrics use the namespace `AIIncidentCopilot/Demo`. Readers may request only `error_rate`, `request_count`, `latency_p95`, `throttles`, `duration`, and `custom_health`. Log filters publish `error_rate` and `request_count` from those JSON lines. The simulator plants the rest of the fixture signals into the same namespace.

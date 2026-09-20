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

---
document_id: svc_orders_api
service: orders-api
document_type: service
severity: medium
version: 1
updated_at: 2026-09-20
---

# orders-api

HTTP API with a fixed database connection pool.

Typical signals are high latency, POOL_EXHAUSTED log lines, and a connection count near the pool maximum while CPU stays low.

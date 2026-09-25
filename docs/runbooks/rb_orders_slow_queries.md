---
document_id: rb_orders_slow_queries
service: orders-api
document_type: runbook
severity: medium
version: 1
updated_at: 2026-09-06
---

# Slow queries on orders-api

Use this runbook when latency rises and the database reports slow statements, while the pool still has free connections.

Do not treat slow queries as pool exhaustion. Capture the statement fingerprint and keep the pool size unchanged until that evidence is reviewed.

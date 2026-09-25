---
document_id: rb_orders_pool_exhaustion
service: orders-api
document_type: runbook
severity: high
version: 2
updated_at: 2026-09-20
---

# Simulated connection pool exhaustion on orders-api

Use this runbook when orders-api latency is high, CPU stays low, and logs contain POOL_EXHAUSTED.

Checked-out connections near the pool maximum mean the pool is saturated. This is not a CPU saturation incident.

Recommend raising the demo pool size by 1. That write is safe only after approval. Do not restart the database from this document.

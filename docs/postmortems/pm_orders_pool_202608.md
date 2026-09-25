---
document_id: pm_orders_pool_202608
service: orders-api
document_type: postmortem
severity: high
version: 1
updated_at: 2026-08-19
---

# Postmortem: orders pool saturation

Latency rose while CPU stayed near 20 percent. Logs contained POOL_EXHAUSTED with checked-out connections at the pool maximum.

The approved change raised the demo pool by 1. CPU scaling would not have addressed the checkout wait.

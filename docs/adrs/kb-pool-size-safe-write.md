---
document_id: kb_adr_pool_size
service: orders-api
document_type: adr
severity: medium
version: 1
updated_at: 2026-09-01
---

# Operational decision: pool size is a safe write

Raising the demo connection pool by 1 is the only pool change this corpus recommends. It still requires approval.

The decision distinguishes pool saturation from CPU saturation so the wrong scaling action is not proposed.

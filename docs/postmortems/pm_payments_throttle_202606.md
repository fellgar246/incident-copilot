---
document_id: pm_payments_throttle_202606
service: payments-api
document_type: postmortem
severity: medium
version: 1
updated_at: 2026-06-18
---

# Postmortem: payments throttling

Throttle counts rose after a client retry change. The service error rate stayed low.

Holding the retry budget stopped the amplification. No rollback was required.

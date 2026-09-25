---
document_id: pm_payments_5xx_202609
service: payments-api
document_type: postmortem
severity: high
version: 1
updated_at: 2026-09-21
---

# Postmortem: payments 5xx after release 2026.09.20.3

Observed evidence showed the 5xx rate and latency moving with the release. Retrieved guidance pointed at the payments rollback runbook. The approved simulated rollback restored the previous version.

Inference that the timeout change caused the upstream errors was recorded separately from the metrics.

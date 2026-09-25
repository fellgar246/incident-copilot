---
document_id: rb_payments_throttling
service: payments-api
document_type: runbook
severity: medium
version: 1
updated_at: 2026-09-12
---

# Throttling on payments-api

Use this runbook when throttle counts rise while the service is otherwise healthy.

Confirm the throttle metric before changing client retry settings. A retry storm can amplify throttling. Recommend holding retries at the current budget until approval.

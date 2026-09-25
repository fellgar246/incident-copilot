---
document_id: rb_payments_retry_storm
service: payments-api
document_type: runbook
severity: medium
version: 1
updated_at: 2026-09-02
---

# Retry storm on payments-api

Use this runbook when client retries multiply a small upstream failure into a large request volume.

Hold the retry budget. Confirm whether throttling is the result or the trigger before recommending a change.

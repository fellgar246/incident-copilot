---
document_id: rb_notifications_lambda_timeout
service: notifications-worker
document_type: runbook
severity: medium
version: 1
updated_at: 2026-09-08
---

# Lambda timeout on notifications-worker

Use this runbook when the worker stops at the Lambda timeout and messages return to the queue.

A timeout with a growing backlog means the handler is too slow for the current batch. Do not raise the timeout and the batch size in the same change. Recommend one approved concurrency step first.

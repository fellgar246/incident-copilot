---
document_id: svc_notifications_worker
service: notifications-worker
document_type: service
severity: medium
version: 1
updated_at: 2026-09-20
---

# notifications-worker

Queue consumer for the notifications SQS queue. The handler runs as a Lambda function.

Typical signals are a growing visible-message count, oldest-message age, worker duration, and Lambda timeouts.

---
document_id: rb_notifications_sqs_backlog
service: notifications-worker
document_type: runbook
severity: medium
version: 2
updated_at: 2026-09-20
---

# SQS backlog on notifications-worker

Use this runbook when visible SQS messages grow and the age of the oldest message exceeds the alarm.

A rising worker duration points at a consumer bottleneck, not a producer outage. Confirm the queue name is notifications before changing concurrency.

Recommend increasing demo worker concurrency by 1 after approval. Do not purge the queue.

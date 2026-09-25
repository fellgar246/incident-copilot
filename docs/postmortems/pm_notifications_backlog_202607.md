---
document_id: pm_notifications_backlog_202607
service: notifications-worker
document_type: postmortem
severity: medium
version: 1
updated_at: 2026-07-22
---

# Postmortem: notifications SQS backlog

Visible messages and oldest-message age climbed together. Worker duration showed the consumer was behind the enqueue rate.

An approved concurrency increase of 1 drained the demo queue. The queue was not purged.

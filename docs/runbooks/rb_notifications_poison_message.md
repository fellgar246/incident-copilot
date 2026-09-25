---
document_id: rb_notifications_poison_message
service: notifications-worker
document_type: runbook
severity: medium
version: 1
updated_at: 2026-09-04
---

# Poison message on the notifications queue

Use this runbook when one message is received repeatedly and the rest of the queue still drains.

Quarantine that message in the demo only after approval. Do not purge the whole queue from this page.

---
document_id: kb_adr_worker_concurrency
service: notifications-worker
document_type: adr
severity: medium
version: 1
updated_at: 2026-09-01
---

# Operational decision: worker concurrency

The demo may recommend increasing notifications-worker concurrency by 1. Purging the queue is out of scope.

Backlog guidance has to cite visible messages and oldest-message age before that recommendation.

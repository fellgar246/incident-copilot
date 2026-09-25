---
document_id: pm_notifications_lambda_202605
service: notifications-worker
document_type: postmortem
severity: medium
version: 1
updated_at: 2026-05-14
---

# Postmortem: Lambda timeout

The worker hit its Lambda timeout and messages became visible again. Raising the timeout without reducing batch work made the backlog worse.

The follow-up kept the timeout and reduced the batch. That sequence is the guidance to reuse.

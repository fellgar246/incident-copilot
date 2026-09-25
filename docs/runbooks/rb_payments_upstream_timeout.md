---
document_id: rb_payments_upstream_timeout
service: payments-api
document_type: runbook
severity: high
version: 1
updated_at: 2026-09-18
---

# Upstream timeout from payments-api

Use this runbook when the payments client waits on billing-api and the error code is an upstream timeout, without a matching release.

Compare the upstream error count with latency. If no release overlaps the window, do not roll back. Collect another log sample and page the dependency owner.

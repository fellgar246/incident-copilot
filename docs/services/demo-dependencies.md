---
document_id: svc_demo_dependencies
service: payments-api
document_type: service
severity: low
version: 1
updated_at: 2026-09-20
---

# Demo dependencies

payments-api calls billing-api. orders-api uses one database pool. notifications-worker reads one SQS queue.

These dependencies are synthetic. Guidance about them stays inside the demo corpus.

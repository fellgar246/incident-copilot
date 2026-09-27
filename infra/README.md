# Infrastructure

`infra/environments/dev` is the only environment. It composes the modules below. State is local until you copy `backend.hcl.example` and migrate.

| Module | Owns |
|---|---|
| `budgets` | USD 5 monthly budget, AI-services budget, alert topic |
| `api` | API Gateway HTTP API and the FastAPI Lambda |
| `events` | EventBridge, SQS, DLQ, incident worker |
| `dynamodb` | incidents and deployments |
| `cloudwatch` | alarms and dashboard |
| `telemetry` | demo log groups |
| `observability` | trace and metric log groups |
| `knowledge-base` | private corpus bucket and knowledge-tool role |
| `iam` | separated roles, including `ci-deploy-role` when OIDC is on |
| `frontend` | private dashboard bucket and CloudFront |

Apply and destroy steps are in the repository README and in [destroy-ephemeral.md](../docs/runbooks/destroy-ephemeral.md).

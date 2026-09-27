# Security model

The model reasons. Tools decide what it can do. A human approves any side effect.

## Tool classes

```text
READ_ONLY    query_logs, query_metrics, get_recent_deployments, search_runbooks
SAFE_WRITE   request_remediation, then POST /incidents/{id}/remediate
DESTRUCTIVE  disabled
```

`SAFE_WRITE` runs only with a valid, unexpired approval. The remediation flips a logical simulator version. It does not restart compute or open a shell. `remediation-tool-role` may `dynamodb:UpdateItem` on the incidents table and explicitly denies EC2, ECS, Lambda mutation, SSM, and load balancer actions.

## What the agent cannot do

- Call AWS with a generic SDK. Each capability is one tool with a schema, a timeout, a quota, and an audit row.
- Invent a tool name and have it run. The gateway catalog is closed.
- Treat logs or retrieved runbooks as instructions. Tool output is untrusted data.
- Continue an investigation after a quota. The stop reason is `COST_OR_USAGE_GUARDRAIL`. The incident row stays.

`AI_ENABLED=false` refuses new agent runs and RAG calls. `GET /health`, `GET /incidents`, `GET /incidents/{id}`, `GET /metrics/costs`, and `GET /evaluations` keep working.

## IAM

Separate roles: `api-role`, `investigation-worker-role`, `agentcore-runtime-role`, `cloudwatch-read-tool-role`, `knowledge-tool-role`, `remediation-tool-role`, `ci-deploy-role`.

GitHub Actions assumes `ci-deploy-role` with OIDC. The trust policy allows the `dev` environment and the `main` branch workflows `ci.yml` and `destroy-ephemeral.yml`. The role cannot create IAM users or access keys. Details are in [ADR-010](../adrs/ADR-010-platform-cicd.md).

## Data leaving the process

Logs are JSON. They may include `request_id`, `incident_id`, `agent_run_id`, `correlation_id`, and `approval_id`. They do not include bearer tokens, AWS credentials, full prompts, or tool secrets. Trace retention in `dev` is 7 days.

## Dashboard

Cost limits on `/settings/costs` are read-only. The browser cannot raise quotas. Approval uses actor `human:demo` in the local demo. There is no Cognito in this version; the API is an interview demo, not a multi-tenant control plane.

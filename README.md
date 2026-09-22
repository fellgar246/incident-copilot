# AI Incident Copilot

Teams lose time correlating alarms, logs, metrics, deployments, and runbooks during an incident. This copilot uses a governed agent to gather evidence through typed tools, retrieve operational knowledge, propose a fix, wait for a human, then act — and measure quality plus estimated cost.

The success criterion is not a convincing model reply. It is a traceable loop:

```text
Detect → Queue → Investigate → Retrieve → Reason → Propose
              → Approve → Act → Observe → Evaluate → Measure cost
```

**AI** sits in AgentCore Runtime. It can only call `query_logs`, `query_metrics`, `get_recent_deployments`, and `search_runbooks` through AgentCore Gateway. It cannot talk to AWS generically.

**AWS** is the real topology: EventBridge and CloudWatch for detection, DynamoDB for state, SQS for investigation jobs, Lambda/API Gateway for HTTP, S3 for the knowledge corpus, Terraform for infra, GitHub OIDC for CI.

**Safety:** `SAFE_WRITE` needs a valid, unexpired approval. Remediation without approval is denied. Destructive actions stay off.

**Quality and cost:** every run records traces, tool calls, tokens, and estimated USD. Evaluations cover diagnosis accuracy, groundedness, and unsafe-action count. Application quotas plus a USD 5 / month `dev` budget cap spend. Design target, not a billing guarantee.

The dashboard is the demo surface. AWS Console is not part of the product flow.

## Current slice

Product contract, foundation, local domain, HTTP + DynamoDB, event-driven ingest, and read-only evidence tools. `query_logs`, `query_metrics`, and `get_recent_deployments` return redacted, size-capped JSON for the demo services. Locally they read simulator fixtures. In AWS, `cloudwatch-read-tool-role` can read only the demo log groups and the `AIIncidentCopilot/Demo` metric namespace. Investigation, the agent runtime, and the dashboard UI land in later slices.

## Repository layout

```text
apps/web                 Next.js dashboard (placeholder)
apps/api                 FastAPI (health, incidents, simulate)
services/                worker, agent, tools, simulator
packages/                contracts, observability, cost-guardrails
docs/                    architecture, ADRs, runbooks, postmortems, services
evals/                   quality gates (placeholder)
fixtures/incidents/      golden simulator snapshots
infra/                   Terraform modules + environments/dev
```

HTTP handlers live in `apps/api`. Persistence is selected with `INCIDENT_REPOSITORY` (`memory` locally, `dynamodb` in AWS). The generated OpenAPI contract is `apps/api/openapi.json`. The ingest worker lives in `services/incident-worker`.

## Prerequisites

- Python 3.12+
- Node 22+
- Terraform 1.6+
- An AWS account on the **Paid** plan if you will later use AgentCore (it is not Free Tier)

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
cp .env.example .env
make ci
```

Never commit `.env`, `*.tfvars`, `backend.hcl`, Terraform state, or AWS credentials. `.env.example` is the source of truth for quota keys.

## Domain simulator (no AWS)

```bash
source .venv/bin/activate
python scripts/seed_demo.py deployment_regression
python scripts/seed_demo.py --write-golden
```

Four deterministic scenarios: `deployment_regression`, `connection_pool_exhaustion`, `queue_backlog`, `false_positive`. The same `--seed` always prints the same IDs, timestamps, and payloads.

## Local HTTP API

```bash
source .venv/bin/activate
make run-api
# GET  http://127.0.0.1:8000/health
# POST http://127.0.0.1:8000/incidents/simulate
#      {"scenario":"deployment_regression","seed":"demo"}
```

`POST /incidents/simulate` accepts `Idempotency-Key` and/or `simulation_id`. The first create is **201**; a matching replay is **200** with the same incident and does not insert a second row. Remaining product routes respond **501** until later slices. Logs are JSON and include `request_id` / `correlation_id`; they never include bearer tokens or AWS credentials.

Set `INCIDENT_REPOSITORY=dynamodb` (and table names from `terraform output`) to point the process at AWS instead of the in-memory store.

## Event ingest

```bash
source .venv/bin/activate
python scripts/trigger_incident.py deployment_regression --seed demo
python scripts/trigger_incident.py --all --ingest-local
# after terraform apply:
python scripts/trigger_incident.py deployment_regression --put-events --bus "$(terraform -chdir=infra/environments/dev output -raw event_bus_name)"
```

`event_id` is the idempotency key: a duplicate event never creates a second incident. The synthetic event stores `correlation_id` on the incident so the trace is recoverable. Poison messages retry three times, then land on the SQS DLQ; CloudWatch alarm `dlq_messages` watches DLQ depth.

`POST /incidents/simulate` is the HTTP test shortcut (direct DynamoDB write). In AWS it also fans out `incident.detected.v1` to EventBridge; the worker no-ops on the duplicate `event_id`.

## Evidence tools

```bash
source .venv/bin/activate
python scripts/seed_telemetry.py deployment_regression --seed demo
python scripts/seed_telemetry.py --all
```

The script seeds the four fixtures into an in-memory store and prints what `query_logs`, `query_metrics`, and `get_recent_deployments` return. The clock is the fixture start plus 10 minutes, so the relative windows cover the seeded samples. Add `--put-cloudwatch` after `terraform apply` to also write logs and custom metrics.

Allowed log input is only `service`, `start_minutes_ago`, `level`, and `limit`. Allowed metrics are `error_rate`, `request_count`, `latency_p95`, `throttles`, `duration`, and `custom_health`. Responses are marked untrusted, redacted, and kept under 12 KB. A free-form query or a service outside `payments-api`, `orders-api`, and `notifications-worker` is rejected.

## Cost guardrails

Design target: **USD 5 / month** for `dev`. This is a design goal, not a billing guarantee.

Hard stops live in the application (`packages/cost-guardrails`):

- Daily incident cap, agent turns, tool calls, RAG calls, token caps, session timeout
- Circuit breakers: `AI_ENABLED`, `AGENT_INVOCATION_ENABLED`, `RAG_ENABLED`, `REMEDIATION_ENABLED`
- When a quota is hit, work stops with `STOP_REASON=COST_OR_USAGE_GUARDRAIL`

AWS Budgets (Terraform module `infra/modules/budgets`):

| Threshold | Type | Severity |
|---|---|---|
| USD 1 | actual | INFO |
| USD 3 | actual | WARNING |
| USD 5 | actual | CRITICAL |
| > USD 5 | forecast | CRITICAL |

Budgets are not real-time kill switches.

## Terraform bootstrap

Follow [docs/runbooks/account-bootstrap.md](docs/runbooks/account-bootstrap.md) once (Paid plan, MFA, region, credits). Then:

```bash
cd infra/environments/dev
cp terraform.tfvars.example terraform.tfvars
# set budget_notification_emails if you want email confirmations
terraform init
terraform plan
terraform apply   # creates budget + SNS; OIDC is off until enable_github_oidc=true
```

State is **local** by default (`terraform.tfstate`, gitignored). Before a shared apply, copy `backend.hcl.example` to `backend.hcl`, switch `versions.tf` to an `s3` backend, and run `terraform init -backend-config=backend.hcl -migrate-state`. Do not check the state file or `backend.hcl` in.

Confirm AgentCore and Managed Knowledge Base availability in the chosen region before later slices. Confirm MFA on the root/account user in the AWS Console once; after that, do not use Console as the product flow.

## GitHub OIDC (no long-lived access keys)

1. Enable MFA on the AWS account / IAM users that can assume admin roles.
2. Copy `terraform.tfvars.example` and set:

   ```hcl
   enable_github_oidc = true
   github_org         = "YOUR_ORG_OR_USER"
   github_repo        = "ai-incident-copilot"
   ```

3. `terraform apply` creates `token.actions.githubusercontent.com` as an OIDC provider and a `ci-deploy` role that can only call `sts:GetCallerIdentity`.
4. In GitHub, add `AWS_ROLE_ARN` as a repository variable pointing at the role output `ci_deploy_role_arn`. Workflows should use `aws-actions/configure-aws-credentials` with `role-to-assume`. Never store `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in GitHub.
5. Deploy permissions are intentionally empty in this skeleton; they are widened later with least privilege.

## IAM roles (target)

```text
api-role
investigation-worker-role
agentcore-runtime-role
cloudwatch-read-tool-role
knowledge-tool-role
remediation-tool-role
ci-deploy-role
```

`api-role` is the API Lambda execution role: CloudWatch logs for that function, Get/Put/Query/Scan/Describe on the incidents and deployments tables, and `events:PutEvents` on the incident bus. `investigation-worker-role` may write the incidents table and read the ingest SQS queue. `cloudwatch-read-tool-role` may filter the demo log groups and read the `AIIncidentCopilot/Demo` metric namespace. `ci-deploy-role` exists only when OIDC is enabled.

## Make targets

| Target | What it runs |
|---|---|
| `make help` | List targets |
| `make lint` | Ruff + ESLint |
| `make fmt` | Ruff format + `terraform fmt` |
| `make typecheck` | mypy + `tsc --noEmit` |
| `make test` | pytest |
| `make terraform-validate` | `terraform init -backend=false` + validate |
| `make run-api` | Uvicorn for `apps/api` |
| `make openapi` | Refresh `apps/api/openapi.json` |
| `make ci` | All of the above except fmt |

## Docs

- [ADR-001 Cost and architecture guardrails](docs/adrs/ADR-001-cost-and-architecture-guardrails.md)
- [ADR-002 Product architecture](docs/adrs/ADR-002-product-architecture.md)
- [ADR-003 HTTP API and DynamoDB persistence](docs/adrs/ADR-003-api-and-persistence.md)
- [ADR-004 Event-driven incident ingest](docs/adrs/ADR-004-event-ingestion.md)
- [ADR-005 Telemetry evidence tools](docs/adrs/ADR-005-telemetry-tools.md)
- [Architecture overview](docs/architecture/overview.md)
- [Demo script](docs/architecture/demo.md)
- [Account bootstrap](docs/runbooks/account-bootstrap.md)

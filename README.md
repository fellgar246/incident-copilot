# AI Incident Copilot

## Problem

Teams lose time correlating alarms, logs, metrics, deployments, and runbooks during an incident.

## Solution

A governed agent gathers evidence through typed tools, retrieves operational knowledge, and proposes a remediation that waits for a human.

## Differentiators

- Tool-based agent
- RAG over a small operational corpus
- Event-driven ingest
- Human approval before any side effect
- Offline evaluations with quality gates
- Application quotas and a circuit breaker
- Per-incident traces, tokens, and estimated cost
- Terraform
- Serverless AWS

An interviewer can answer six questions from this page: what problem it solves, how it uses AI, how it uses AWS, how it blocks dangerous actions, how quality is measured, and what a demo session costs.

```text
Detect → Queue → Investigate → Retrieve → Reason → Propose
              → Approve → Act → Observe → Evaluate → Measure cost
```

Diagram: [docs/architecture/diagram.md](docs/architecture/diagram.md).

## How it uses AI

AgentCore Runtime runs one agent. The only model calls go through a Bedrock adapter (`BEDROCK_MODEL_ID`, default Nova Micro). The agent may call `query_logs`, `query_metrics`, `get_recent_deployments`, `search_runbooks`, and `request_remediation` via AgentCore Gateway. It cannot talk to AWS with a generic SDK, and it cannot execute the remediation itself.

`request_remediation` records a proposal. `POST /incidents/{id}/remediate` returns 403 `DENIED` unless that proposal has a valid, unexpired approval. The write flips a logical simulator version. It does not restart cloud resources.

## How it uses AWS

EventBridge and CloudWatch detect. DynamoDB stores the incident. SQS buffers the worker. Lambda and API Gateway serve HTTP. S3 holds the corpus and the static dashboard. CloudFront serves the dashboard. Terraform creates the stack. GitHub Actions assumes `ci-deploy-role` with OIDC.

The dashboard is the demo surface. AWS Console is not part of the product flow. The interviewer script is [docs/architecture/demo.md](docs/architecture/demo.md): **Run simulation**, **Investigate**, **Execute remediation** (denied), **Approve**, **Execute remediation** again.

## How dangerous actions are blocked

`READ_ONLY` tools run inside quotas. `SAFE_WRITE` needs a human approval. `DESTRUCTIVE` actions are off. Logs and retrieved pages are untrusted data. A reached quota stops new AI work with `STOP_REASON=COST_OR_USAGE_GUARDRAIL` and keeps the incident. `AI_ENABLED=false` keeps the read APIs up. Full write-up: [docs/architecture/security-model.md](docs/architecture/security-model.md).

## How quality is measured

Offline cases in `evals/incidents.jsonl` score diagnosis accuracy, required-evidence recall, groundedness, and unsafe-action count. CI runs the PR subset on pull requests and the release profile on `main`. The latest summary is `GET /evaluations`. Targets: unsafe-action rate 0, diagnosis accuracy at least 85%, required-evidence recall at least 90%. The checked-in full run is at 1.0 / 1.0 / 1.0 with zero unsafe actions. That run is scripted and offline. It is not a claim about a live model.

## What a demo session costs

Design target for `dev`: **USD 5 / month**. That is a target, not a billing guarantee. AWS Budgets alert at USD 1, 3, and 5. They do not hard-stop spend. The hard stop is the application.

Observed cost of one `deployment_regression` diagnosis, from the offline suite at Nova Micro list price: **USD 0.00046039**. The 24-case suite is **USD 0.00920775**. These are not an AWS invoice. After a live session, compare the hour in Cost Explorer and update this paragraph if the bill differs. Checklist: [docs/runbooks/cost-explorer-review.md](docs/runbooks/cost-explorer-review.md).

| Component | Monthly design target (dev) |
|---|---:|
| Lambda, API, SQS, EventBridge, DynamoDB, S3 | USD 0–0.50 |
| CloudWatch | USD 0–0.75 |
| Managed knowledge base storage | USD 0.05–0.25 |
| Managed knowledge base retrieval | USD 0.05–0.50 |
| AgentCore Gateway | USD 0.01–0.10 |
| AgentCore Runtime | USD 0.10–1.00 |
| Bedrock inference | USD 0.50–2.50 |
| Evaluations | USD 0.05–0.50 |
| **Target** | **≤ USD 5** |

If a real bill crosses the target: turn off continuous evaluations, lower incidents per day, lower `MAX_AGENT_TURNS`, lower tool calls and context, lower logs consulted, switch to a cheaper model, turn RAG off outside tests, then review Cost Explorer. `python scripts/estimate_cost.py` prints the same order.

## Trade-offs

**DynamoDB vs RDS.** Incident state is a small item plus a timeline. DynamoDB is pay-per-request and scales to zero. RDS would be a standing instance.

**Managed Knowledge Base vs OpenSearch.** The corpus is tens of megabytes. Managed KB storage is about USD 5 per GB-month, so this corpus is cents. A dedicated OpenSearch collection has a minimum that misses the USD 5 target. The provider cannot create a KB without that collection, so retrieval uses a local index until a base id is set. Upload stays in `scripts/sync_knowledge.py` (dry-run by default).

**Lambda vs ECS.** HTTP and the worker are idle almost all month. Lambda bills per millisecond. ECS would be a service to keep warm.

**Single agent vs multi-agent.** One agent is enough to evaluate. Splitting investigation, remediation, and communications waits until one agent is actually hard to score.

**No NAT Gateway in dev.** The functions are not in a VPC. A NAT Gateway is about USD 32 / month before data processing, which spends the monthly target by itself. Private connectivity is backlog, with that cost written down first.

**Short retention.** Logs and traces live 7 days in `dev`.

**No automatic destructive remediation.** The only write is a simulated rollback, and only after approval.

## v1 surface

`GET /metrics/costs` and `GET /incidents/{id}/agent-runs` return estimated cost, tokens, tool calls, runtime, and RAG calls. Trace and metric log groups retain data for 7 days. `remediation-tool-role` is limited to an incident-item update and explicitly denies compute and shell actions.

Later work, including Cognito and a real Slack or PagerDuty hook, is in [docs/backlog.md](docs/backlog.md). Release risks and how they are mitigated: [docs/architecture/release-risks.md](docs/architecture/release-risks.md).

## Repository layout

```text
apps/web                 Next.js dashboard (static export)
apps/api                 FastAPI (health, incidents, simulate)
services/                worker, agent, tools, simulator
packages/                contracts, observability, cost-guardrails
docs/                    architecture, ADRs, runbooks, postmortems, services
evals/                   versioned cases, gates, and the latest run summary
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

## Dashboard demo

The interviewer path runs in the UI. AWS Console is not required to read the incident.

```bash
source .venv/bin/activate
make run-api
# second terminal
npm run dev -w web
```

Open http://localhost:3000/incidents. With an empty store the page shows **No incidents yet**. **Run simulation** posts `deployment_regression`. The other scenarios are in the secondary menu.

On the incident page: **Investigate**, then open Investigation, Evidence, and Retrieved Knowledge. **Execute remediation** before approval shows **Denied — missing valid approval** and a red timeline row. **Approve** (actor `human:demo`) then **Execute remediation** moves the incident to `RESOLVED`. Cost and Trace show tokens, tool calls, estimated USD, and `agent_run_id`. Evaluations and Settings / Costs are in the left nav. Cost limits are read-only.

`/incidents/[id]` is exported as a static shell (`/incidents/_/`). CloudFront rewrites real ids onto that shell, so the dashboard stays on S3 + CloudFront with no Lambda. After `terraform apply`:

```bash
npm run build -w web
aws s3 sync apps/web/out "s3://$(terraform -chdir=infra/environments/dev output -raw web_bucket_name)" --delete
aws cloudfront create-invalidation --distribution-id "$(terraform -chdir=infra/environments/dev output -raw web_distribution_id)" --paths "/*"
```

Set `NEXT_PUBLIC_API_BASE_URL` to the `api_endpoint` output before the production build, and add the CloudFront origin to `CORS_ORIGINS`.

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

`POST /incidents/simulate` accepts `Idempotency-Key` and/or `simulation_id`. The first create is **201**; a matching replay is **200** with the same incident and does not insert a second row. Approve, reject, and remediate also require `Idempotency-Key`. Remediate without a grant is **403**. `GET /evaluations` returns the latest offline run: pass rate, diagnosis accuracy, groundedness, unsafe action count, average tool calls, and average estimated cost. `GET /metrics/costs` returns the system and AI series, including estimated USD per incident. Logs are JSON and include `request_id`, `incident_id`, `agent_run_id`, `correlation_id`, and `approval_id`. They never include bearer tokens, AWS credentials, full prompts, or tool secrets.

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

Hard stops live in the application (`packages/cost-guardrails`):

- Daily incident cap, agent turns, tool calls, RAG calls, token caps, session timeout
- Circuit breakers: `AI_ENABLED`, `AGENT_INVOCATION_ENABLED`, `RAG_ENABLED`, `REMEDIATION_ENABLED`
- When a quota is hit, work stops with `STOP_REASON=COST_OR_USAGE_GUARDRAIL` and no further model calls are made
- `AI_ENABLED=false` leaves `GET /health`, `GET /incidents`, `GET /metrics/costs`, and `GET /evaluations` working

AWS Budgets (Terraform module `infra/modules/budgets`):

| Threshold | Type | Severity |
|---|---|---|
| USD 1 | actual | INFO |
| USD 3 | actual | WARNING |
| USD 5 | actual | CRITICAL |
| > USD 5 | forecast | CRITICAL |

```bash
python scripts/estimate_cost.py
python scripts/verify_quotas.py
```

Cleanup of a `dev` or `ephemeral-*` stack: [docs/runbooks/destroy-ephemeral.md](docs/runbooks/destroy-ephemeral.md). Dry-run:

```bash
python scripts/cleanup_dev.py --environment dev
```

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

The first apply is still a human with an admin role. After that, GitHub assumes `ci-deploy-role`.

1. Enable MFA on the AWS account / IAM users that can assume admin roles.
2. Create the remote state bucket and lock table described in `backend.hcl.example`.
3. Copy `terraform.tfvars.example` and set:

   ```hcl
   enable_github_oidc     = true
   github_org             = "YOUR_ORG_OR_USER"
   github_repo            = "ai-incident-copilot"
   github_environment     = "dev"
   terraform_state_bucket = "YOUR_STATE_BUCKET"
   terraform_lock_table   = "ai-incident-copilot-tf-locks"
   ```

4. `terraform apply` creates the OIDC provider and `ci-deploy-role`. The role can manage this stack's prefixed resources. It cannot create IAM users or access keys. `Resource=*` is only used where the AWS API requires it (listed in `infra/modules/iam/ci_deploy.tf`).
5. Create the GitHub environment `dev` with a required reviewer. Store `AWS_ROLE_ARN`, `TF_STATE_BUCKET`, `TF_LOCK_TABLE`, and `TF_TFVARS` as repository variables. Steps: [docs/runbooks/github-environment.md](docs/runbooks/github-environment.md).
6. Workflows use `aws-actions/configure-aws-credentials` with `role-to-assume`. Never store `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in GitHub.

Pull requests run lint, typecheck, unit tests, integration tests, the secret scan, offline evals, and `terraform validate`. They do not assume the AWS role. A push to `main` plans and applies only after the `dev` environment is approved and those variables exist. The plan file is applied on the same runner because the Lambda zip hash includes file timestamps. Smoke then calls health, simulate, investigate when AI is on, a denied remediation, approve, and the approved remediation.

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

`api-role` is the API Lambda execution role: CloudWatch logs for that function, Get/Put/Query/Scan/Describe on the incidents and deployments tables, and `events:PutEvents` on the incident bus. `investigation-worker-role` may write the incidents table and read the ingest SQS queue. `cloudwatch-read-tool-role` may filter the demo log groups and read the `AIIncidentCopilot/Demo` metric namespace. `knowledge-tool-role` may read the corpus bucket and call `bedrock:Retrieve`. `ci-deploy-role` exists only when OIDC is enabled and is the role GitHub assumes.

## Make targets

| Target | What it runs |
|---|---|
| `make help` | List targets |
| `make lint` | Ruff + ESLint |
| `make fmt` | Ruff format + `terraform fmt` |
| `make typecheck` | mypy + `tsc --noEmit` |
| `make test` | pytest (unit and integration) |
| `make test-unit` | pytest excluding moto-backed tests |
| `make test-integration` | moto-backed pytest |
| `make security` | secret scan |
| `make terraform-validate` | `terraform init -backend=false` + validate |
| `make run-api` | Uvicorn for `apps/api` |
| `make openapi` | Refresh `apps/api/openapi.json` |
| `make eval` | Offline PR evaluation subset |
| `make eval-full` | Full offline evaluation suite |
| `make estimate-cost` | Demo-session estimate and design envelope |
| `make verify-quotas` | Load quotas and check the circuit breaker |
| `make ci` | Lint, typecheck, test, security, PR eval gates, terraform-validate |

## Docs

- [ADR-001 Cost and architecture guardrails](docs/adrs/ADR-001-cost-and-architecture-guardrails.md)
- [ADR-002 Product architecture](docs/adrs/ADR-002-product-architecture.md)
- [ADR-003 HTTP API and DynamoDB persistence](docs/adrs/ADR-003-api-and-persistence.md)
- [ADR-004 Event-driven incident ingest](docs/adrs/ADR-004-event-ingestion.md)
- [ADR-005 Telemetry evidence tools](docs/adrs/ADR-005-telemetry-tools.md)
- [ADR-009 Offline evaluations](docs/adrs/ADR-009-evaluations.md)
- [ADR-010 Platform CI/CD and release](docs/adrs/ADR-010-platform-cicd.md)
- [Architecture overview](docs/architecture/overview.md)
- [Diagram](docs/architecture/diagram.md)
- [Security model](docs/architecture/security-model.md)
- [Release risks](docs/architecture/release-risks.md)
- [Demo script](docs/architecture/demo.md)
- [Account bootstrap](docs/runbooks/account-bootstrap.md)
- [GitHub environment](docs/runbooks/github-environment.md)
- [Cost Explorer review](docs/runbooks/cost-explorer-review.md)
- [Destroy dev](docs/runbooks/destroy-ephemeral.md)
- [Backlog](docs/backlog.md)

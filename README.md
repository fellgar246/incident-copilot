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

Product contract plus foundation and local domain: architecture/API/data/dashboard catalogs, monorepo toolchains, application quotas, AWS Budget bootstrap, GitHub OIDC skeleton, ADR-001/002, incident state machine, and a deterministic simulator. HTTP, agent runtime, and dashboard UI land in later slices.

## Repository layout

```text
apps/web                 Next.js dashboard (placeholder)
apps/api                 FastAPI (placeholder)
services/                worker, agent, tools, simulator
packages/                contracts, observability, cost-guardrails
docs/                    architecture, ADRs, runbooks, postmortems, services
evals/                   quality gates (placeholder)
fixtures/incidents/      golden simulator snapshots
infra/                   Terraform modules + environments/dev
specs/                   Spec-driven development package
```

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

Never commit `.env`, `*.tfvars`, or AWS credentials. `.env.example` is the source of truth for quota keys.

## Domain simulator (no AWS)

```bash
source .venv/bin/activate
python scripts/seed_demo.py deployment_regression
python scripts/seed_demo.py --write-golden
```

Four deterministic scenarios: `deployment_regression`, `connection_pool_exhaustion`, `queue_backlog`, `false_positive`. The same `--seed` always prints the same IDs, timestamps, and payloads.

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

```bash
cd infra/environments/dev
cp terraform.tfvars.example terraform.tfvars
# set budget_notification_emails if you want email confirmations
terraform init
terraform plan
terraform apply   # creates budget + SNS; OIDC is off until enable_github_oidc=true
```

State is **local** by default (`terraform.tfstate`, gitignored). Plan an S3 backend with a DynamoDB lock table before anyone else applies this stack. Do not check the state file in.

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

Only `ci-deploy-role` exists in this bootstrap, and only when OIDC is enabled.

## Make targets

| Target | What it runs |
|---|---|
| `make help` | List targets |
| `make lint` | Ruff + ESLint |
| `make fmt` | Ruff format + `terraform fmt` |
| `make typecheck` | mypy + `tsc --noEmit` |
| `make test` | pytest |
| `make terraform-validate` | `terraform init -backend=false` + validate |
| `make ci` | All of the above except fmt |

## Docs

- [ADR-001 Cost and architecture guardrails](docs/adrs/ADR-001-cost-and-architecture-guardrails.md)
- [ADR-002 Product architecture](docs/adrs/ADR-002-product-architecture.md)
- [Architecture overview](docs/architecture/overview.md)
- [Demo script](docs/architecture/demo.md)
- Specs in [`specs/`](specs/00-constitution.md)

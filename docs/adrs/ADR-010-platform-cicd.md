# ADR-010 — Platform CI/CD and release

- **Status:** accepted
- **Date:** 2026-09-26
- **Deciders:** project owner

## Context

A new account should be able to recreate `dev` from the repository README and Terraform. GitHub Actions must not store long-lived AWS keys. AWS Budgets are not a real-time kill switch. The pinned AWS provider (`~> 5.70`) cannot declare AgentCore Gateway or a Managed Knowledge Base without an OpenSearch collection.

The Lambda archive hash includes file modification times, so a saved plan has to be applied on the runner that created it.

## Decision

1. **OIDC.** `ci-deploy-role` trusts `token.actions.githubusercontent.com`. The subject must be `repo:<org>/<repo>:environment:dev`. The workflow ref must be `ci.yml` or `destroy-ephemeral.yml` on `main`. A job that does not set the `dev` environment cannot assume the role. Pull request workflows cannot assume it either.
2. **Manual gate.** The deploy and destroy jobs set `environment: dev`. Required reviewers are a GitHub environment setting, not a key in the workflow file. See [GitHub environment](../runbooks/github-environment.md).
3. **Least privilege.** The role can manage resources named `ai-incident-copilot-dev-*`, the GitHub OIDC provider, and an optional remote state bucket. It denies `iam:CreateUser` and `iam:CreateAccessKey`. `Resource=*` is limited to APIs that reject resource ARNs: `sts:GetCallerIdentity`, a short list of `List*`/`Describe*` calls, and CloudFront creates. Those exceptions are comments in `infra/modules/iam/ci_deploy.tf`.
4. **Pipeline.** On every push and pull request: install, lint, typecheck, unit tests, integration tests (moto), secret scan, offline evaluations, `terraform fmt` / `validate`. On `main`, after the `dev` environment is approved and the remote-state variables are set: plan, apply that plan, publish the static dashboard, smoke-test the API.
5. **Fail closed.** Plan and apply do not run unless `AWS_ROLE_ARN`, `TF_STATE_BUCKET`, `TF_LOCK_TABLE`, and `TF_TFVARS` are repository variables. Missing variables skip the job. They do not fall back to an empty local state.
6. **Destroy.** `scripts/cleanup_dev.py` refuses any environment other than `dev` or `ephemeral-*`. Apply also requires `DESTROY_EPHEMERAL=1` and `--confirm destroy-dev`. The workflow `destroy-ephemeral.yml` uses the same environment gate. No resource sets `prevent_destroy`. The web and corpus buckets set `force_destroy` so a destroy can empty them.
7. **Modules.** Directories stay as they are so existing state addresses do not move:

   | Directory | What it owns |
   |---|---|
   | `budgets` | monthly budget, AI services budget, SNS |
   | `api` | HTTP API and the FastAPI Lambda |
   | `events` | EventBridge bus, SQS queue, DLQ, incident worker |
   | `dynamodb` | incidents and deployments tables |
   | `cloudwatch` | alarms and the operations dashboard |
   | `telemetry` | demo log groups and metric filters |
   | `observability` | trace and metric log groups |
   | `knowledge-base` | private corpus bucket and `knowledge-tool-role` |
   | `iam` | runtime, tool, worker, and CI roles |
   | `frontend` | private S3 bucket and CloudFront |

8. **Non-declarative debt.** `scripts/register_gateway.py` registers the Gateway because the provider has no Gateway resource (ADR-006). `scripts/sync_knowledge.py` uploads the corpus and can start one ingestion job; it does not create a vector store (ADR-007). Both default to dry-run.
9. **Quotas stay in the application.** Hitting a quota sets `STOP_REASON=COST_OR_USAGE_GUARDRAIL` and does not start another AI run. `AI_ENABLED=false` leaves read APIs up. Budgets remain alerts.

## Cost impact

- The design envelope for `dev` stays at most USD 5 / month. That is a target, not an invoice.
- One offline `deployment_regression` diagnosis is about USD 0.00046 at Nova Micro list price. The full offline suite is about USD 0.009. Neither number is an AWS bill.
- NAT Gateway, RDS, and a dedicated OpenSearch collection stay out. A single NAT Gateway is on the order of USD 32 / month before data processing, which would miss the target on its own.
- If a real bill crosses the target, mitigate in the order printed by `scripts/estimate_cost.py`, then review Cost Explorer.

## Security impact

- No static `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in GitHub.
- CI cannot create IAM users or access keys.
- Destroy cannot target a name other than `dev` or `ephemeral-*`.
- Remediation without a valid approval stays denied. Destructive actions stay off.

## Review date

Revisit when the AWS provider can declare Gateway and Knowledge Base resources, and before the first shared apply from GitHub.

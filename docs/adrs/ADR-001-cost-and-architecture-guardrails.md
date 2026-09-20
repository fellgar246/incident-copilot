# ADR-001 — Cost and architecture guardrails

- **Status:** accepted
- **Date:** 2026-09-20
- **Deciders:** project owner

## Context

The development environment has a design target of **USD 5 / month**. Amazon Bedrock AgentCore is billed on the Paid plan (microVM vCPU/memory time plus Gateway invocations). Managed Knowledge Base storage is billed per GB-month. AWS Budgets refresh a few times per day, so they cannot hard-stop spend in real time.

The product still needs a production-shaped architecture: serverless APIs, event-driven ingestion, a governed agent, RAG over a small corpus, and a static dashboard.

## Decision

1. **Serverless by default.** Prefer Lambda, API Gateway, DynamoDB, SQS, EventBridge, S3, CloudFront, and pay-per-active-time agent runtime. Any always-on component requires a later ADR with cost justification.
2. **Application quotas are the hard stop.** Limits live in environment configuration (see `.env.example`), not scattered constants. Hitting a quota sets `STOP_REASON=COST_OR_USAGE_GUARDRAIL` and preserves the incident without further AI spend.
3. **Circuit breakers.** `AI_ENABLED`, `AGENT_INVOCATION_ENABLED`, `RAG_ENABLED`, and `REMEDIATION_ENABLED` can disable generation independently of read APIs.
4. **AWS Budget of USD 5** with actual alerts at USD 1 (INFO), USD 3 (WARNING), USD 5 (CRITICAL), plus a forecast alert above USD 5. Optional second budget filtered to Bedrock. Budgets are signals, not runtime enforcement.
5. **IAM roles are separated** (`api-role`, `investigation-worker-role`, `agentcore-runtime-role`, tool roles, `ci-deploy-role`). Least privilege; GitHub Actions uses OIDC, never long-lived access keys.
6. **Human-in-the-loop.** `SAFE_WRITE` actions require a valid, unexpired approval. `DESTRUCTIVE` actions stay disabled in v1.
7. **No generic AWS access for the agent.** Each capability is a typed tool with schema, validation, timeout, quota, and audit.
8. **Out of v1 unless a later ADR reopens it:** NAT Gateway, RDS/Aurora, self-managed OpenSearch, ECS/Fargate always-on, EKS, provisioned concurrency, AgentCore Browser/Code Interpreter/Web Search/long-term Memory, real PagerDuty/Slack/Jira, multi-agent orchestration, Bedrock provisioned throughput, customer-managed KMS when an AWS-managed key is enough.

## Cost impact

- Design target remains USD 5 / month for `dev`; this is not a billing guarantee.
- Managed Knowledge Base storage is kept small (tens of MB of raw corpus).
- Agent sessions are bounded (`MAX_SESSION_SECONDS`, turn/tool/token caps).
- Log retention is 7 days in `dev`.

## Security impact

- No secrets in git; `.env` and Terraform state are ignored.
- OIDC for CI removes persistent AWS access keys from GitHub.
- Remediation cannot run without approval; destructive tools are off.
- Tool IAM is scoped per capability rather than a shared admin role.

## Review date

Revisit before the first shared `dev` apply, and whenever AgentCore or Bedrock regional pricing changes.

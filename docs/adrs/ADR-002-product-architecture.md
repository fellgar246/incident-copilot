# ADR-002 — Product architecture

- **Status:** accepted
- **Date:** 2026-09-20
- **Deciders:** project owner

## Context

Teams lose time correlating alarms, logs, metrics, deployments, and runbooks during an incident. A portfolio copilot has to show that the model sits inside a real architecture — not a chatbot wrapped in AWS logos — while staying inside a USD 5 / month design target for `dev`.

The product also has to be demoable without AWS Console. An interviewer should see the loop Detect → Queue → Investigate → Retrieve → Reason → Propose → Approve → Act → Observe → Evaluate → Measure cost on a dashboard.

## Decision

1. **Target topology.** Next.js (S3 + CloudFront) talks to FastAPI on Lambda via API Gateway. DynamoDB holds incident state and append-only events. EventBridge + SQS drive investigation jobs. Bedrock AgentCore Runtime runs the agent; AgentCore Gateway exposes typed tools (CloudWatch, deployments, knowledge). Remediation is a separate SAFE_WRITE tool behind human approval.
2. **Lifecycle.** Incidents move through DETECTED → QUEUED → INVESTIGATING → DIAGNOSED → REMEDIATION_PROPOSED → AWAITING_APPROVAL → APPROVED → REMEDIATING → RESOLVED, with REJECTED and FAILED as terminal branches. Every transition records timestamp and actor. Illegal transitions raise.
3. **Data.** `PK = INCIDENT#{incident_id}` for incidents; `SK = EVENT#{timestamp}#{event_id}` for events. Deployments are a small metadata table so the demo can correlate releases without CodeDeploy or ECS.
4. **HTTP surface.** The minimum API is health, incident list/detail/events, simulate, investigate, approve, reject, remediate, agent-runs, cost metrics, and evaluations. Mutable calls require `Idempotency-Key`.
5. **Dashboard surface.** `/incidents`, `/incidents/[id]`, `/evaluations`, `/settings/costs`. Cost limits are read-only from an unauthorized session.
6. **Demo services.** `payments-api`, `orders-api`, `notifications-worker`. Primary script: `deployment_regression`.
7. **No generic AWS access for the agent.** Investigation tools are `query_logs`, `query_metrics`, `get_recent_deployments`, and `search_runbooks`.

This ADR does not implement HTTP, AWS resources, or UI. Later slices fill those in against this contract. Changing the API, states, or topology requires an ADR amendment.

## Cost impact

- Serverless by default; no always-on compute in v1.
- Agent work is bounded by application quotas and circuit breakers (ADR-001).
- Knowledge corpus stays small (runbooks, ADRs, postmortems).

## Security impact

- Side-effecting tools need a valid, unexpired `approval_id`.
- Destructive actions stay disabled in v1.
- Audit trail is append-only; consumers are idempotent.
- Cost limits cannot be raised from the dashboard session.

## Review date

Revisit when the first HTTP slice lands, or if AgentCore/Gateway topology changes.

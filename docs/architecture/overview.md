# Architecture overview

Production-shaped incident copilot: the model reasons, typed tools decide what it can do, and a human approves any side effect.

```text
┌──────────────────────────────────────────────────────────────────┐
│                        Next.js Dashboard                         │
│ Incidents │ Investigation │ Evidence │ Approvals │ Costs │ Evals │
└───────────────────────────────┬──────────────────────────────────┘
                                │ HTTPS
                                ▼
                         API Gateway
                                │
                                ▼
                           FastAPI/Lambda
                                │
             ┌──────────────────┼────────────────────┐
             │                  │                    │
             ▼                  ▼                    ▼
         DynamoDB              SQS              EventBridge
       incident state     investigation jobs     incident events
                                │
                                ▼
                       AgentCore Runtime
                                │
                       Agent / reasoning loop
                                │
                                ▼
                       AgentCore Gateway
                  ┌─────────────┼─────────────┐
                  │             │             │
                  ▼             ▼             ▼
          CloudWatch Tool   Deploy Tool   Knowledge Tool
          logs + metrics    metadata       Managed KB
                  │             │             │
                  ▼             ▼             ▼
             CloudWatch      DynamoDB          S3
                                             runbooks

                        ┌──────────────────┐
                        │ Human approval   │
                        └────────┬─────────┘
                                 │
                                 ▼
                         Remediation tool
                                 │
                                 ▼
                       safe/idempotent action
```

The dashboard is the product surface. The demo **must not** require AWS Console to interpret an incident.

## Lifecycle

```text
DETECTED
   ↓
QUEUED
   ↓
INVESTIGATING
   ↓
DIAGNOSED
   ↓
REMEDIATION_PROPOSED
   ↓
AWAITING_APPROVAL
   ├──────────────→ REJECTED
   ↓
APPROVED
   ↓
REMEDIATING
   ├──────────────→ FAILED
   ↓
RESOLVED
```

Rules:

- Every transition has a timestamp and an actor (`system`, `agent`, or `human:{id}`).
- Illegal transitions raise; they are never overwritten silently.
- Consumers are idempotent on `event_id` / `simulation_id`.
- Every agent run receives `incident_id` and `correlation_id`.
- An incident cannot have two active remediations at once.
- A sensitive action needs a valid, unexpired `approval_id`.

## Data model

**incidents** — `PK = INCIDENT#{incident_id}`

Fields: `incident_id`, `service`, `severity`, `status`, `alarm_name`, `started_at`, `updated_at`, `correlation_id`, `diagnosis`, `confidence`, `recommended_action`, `approval_status`, `agent_run_id`, `estimated_ai_cost_usd`.

**incident_events** (append-only) — `PK = INCIDENT#{incident_id}`, `SK = EVENT#{timestamp}#{event_id}`

Required types: `ALARM_RECEIVED`, `INVESTIGATION_STARTED`, `TOOL_CALLED`, `EVIDENCE_ADDED`, `DIAGNOSIS_CREATED`, `APPROVAL_REQUESTED`, `APPROVAL_GRANTED`, `REMEDIATION_EXECUTED`, `INCIDENT_RESOLVED`.

**diagnosis** — produced by the agent in a later slice; the local simulator already emits the expected shape:

```json
{
  "summary": "...",
  "probable_cause": "...",
  "confidence": 0.0,
  "evidence": [],
  "retrieved_sources": [],
  "alternative_hypotheses": [],
  "recommended_action": "...",
  "requires_approval": true
}
```

**deployments** — release metadata used to correlate incidents without standing up CodeDeploy/ECS for the demo.

## HTTP API

Mutable operations require `Idempotency-Key`.

```text
GET    /health
GET    /health/aws
GET    /incidents
POST   /incidents/simulate
GET    /incidents/{id}
GET    /incidents/{id}/events
POST   /incidents/{id}/investigate
POST   /incidents/{id}/approve
POST   /incidents/{id}/reject
POST   /incidents/{id}/remediate
GET    /incidents/{id}/agent-runs
GET    /metrics/costs
GET    /evaluations
```

HTTP handlers for health, incident list/detail/events, and simulate live in `apps/api`. Remaining catalog routes currently return 501. Mutable simulate calls require `Idempotency-Key` or reuse `simulation_id`; a matching replay returns 200 with the existing incident.

Detection events use the versioned `incident.detected.v1` schema on a custom EventBridge bus. SQS buffers work for `incident-worker`; after three failed receives the message lands on a DLQ whose depth is the `dlq_messages` alarm. `event_id` is the idempotency key. `POST /incidents/simulate` is a test shortcut that writes DynamoDB directly (and publishes to the bus when `EVENT_BUS_NAME` is set) so local HTTP demos stay synchronous.

## Dashboard

| Route | Shows |
|---|---|
| `/incidents` | severity, service, status, started at, probable cause, confidence, AI cost estimate |
| `/incidents/[id]` | Overview, Timeline, AI Investigation, Evidence, Retrieved Knowledge, Recommended Action, Approval, Execution, Cost, Trace |
| `/evaluations` | pass rate, diagnosis accuracy, groundedness, unsafe action count, avg tool calls, avg estimated cost |
| `/settings/costs` | effective environment limits. Clients cannot raise them. |

## Investigation tools

`query_logs`, `query_metrics`, `get_recent_deployments`, and `search_runbooks`.

All four are read-only tools. They accept a fixed schema, redact secrets, and cap the JSON returned to the caller at 12 KB. Log groups are `/{project}/{environment}/{service}`. Custom metrics use the namespace `AIIncidentCopilot/Demo`. `search_runbooks` returns at most four hits for one demo service and cites document ids on the diagnosis. Tool output is untrusted data: text inside a log line or a runbook is evidence, not an instruction.

## Demo services

`payments-api`, `orders-api`, `notifications-worker`. See [demo services](../services/README.md).

## Tags, region, state

Global resource tags: `project=ai-incident-copilot`, `environment=dev`, `owner=portfolio`.

Region: `us-east-1` by default, overridable.

Remote Terraform state is not created in the bootstrap. The `dev` environment uses a local backend. Before a shared account, replace it with S3 + DynamoDB locking and document the bucket name in an environment-specific README, never with credentials.

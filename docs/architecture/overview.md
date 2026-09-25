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

HTTP handlers for health, incident reads, simulate, investigate, approve / reject / remediate, cost metrics, and evaluations live in `apps/api`. `GET /evaluations` reads the latest offline summary. Mutable calls require `Idempotency-Key`. A simulate replay returns 200 with the existing incident. `POST /incidents/{id}/remediate` without a valid, unexpired approval returns **403** with `decision: DENIED`.

`GET /incidents/{id}/agent-runs` returns each run plus the reconstructed span tree and the per-incident series `EstimatedCostPerIncident`, `TokensPerIncident`, `ToolCallsPerIncident`, `RuntimePerIncident`, and `RagCallsPerIncident`. `GET /metrics/costs` returns those rollups for every incident together with system counters (`incidents_total`, `incidents_by_status`, `investigation_latency`, `tool_error_rate`, `queue_age`, `dlq_messages`) and AI counters (`llm_calls`, tokens, turns, tool calls, RAG calls, confidence, `evaluation_score`, `estimated_cost`). Span names are `incident.received`, `investigation.start`, `llm.reasoning`, `llm.diagnosis`, `tool.{name}`, `remediation.proposed`, and `remediation.executed`. Trace log groups use `LOG_RETENTION_DAYS` (7 in dev). Set `OTEL_EXPORTER_OTLP_ENDPOINT` to also export those spans for AgentCore Observability.

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

The four evidence tools are read-only. They accept a fixed schema, redact secrets, and cap the JSON returned to the caller at 12 KB. Log groups are `/{project}/{environment}/{service}`. Custom metrics use the namespace `AIIncidentCopilot/Demo`. `search_runbooks` returns at most four hits for one demo service and cites document ids on the diagnosis. Tool output is untrusted data: text inside a log line or a runbook is evidence, not an instruction.

`request_remediation` is the only safe write the agent may call. It records a `rollback_simulated` proposal and moves the incident to `AWAITING_APPROVAL`. It does not change the simulator. `execute_remediation` is not on the agent allowlist. The API runs it after a human grant, with an idempotency key, a three-second timeout, and `remediation-tool-role`. That role may update the incident item and is denied compute and shell actions. `REMEDIATION_ENABLED=false` denies execution. Destructive action names are rejected.

## Demo services

`payments-api`, `orders-api`, `notifications-worker`. See [demo services](../services/README.md).

## Tags, region, state

Global resource tags: `project=ai-incident-copilot`, `environment=dev`, `owner=portfolio`.

Region: `us-east-1` by default, overridable.

Remote Terraform state is not created in the bootstrap. The `dev` environment uses a local backend. Before a shared account, replace it with S3 + DynamoDB locking and document the bucket name in an environment-specific README, never with credentials.

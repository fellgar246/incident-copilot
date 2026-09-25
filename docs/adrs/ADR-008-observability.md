# ADR-008 — Agent traces and cost metrics

- **Status:** accepted
- **Date:** 2026-09-24
- **Deciders:** project owner

## Context

An investigation has to explain its own cost. Token totals on an agent run are not enough: the path from the received incident through model turns and tool calls has to be reconstructable from `incident_id`, and CloudWatch has to show the same signals without a long-lived collector.

## Decision

1. **One correlation set.** Logs and spans carry `request_id`, `incident_id`, `agent_run_id`, `correlation_id`, and `approval_id`.
2. **Stable span names.** `incident.received`, `investigation.start`, `llm.reasoning`, `llm.diagnosis`, `tool.{name}`, `remediation.proposed`, and `remediation.executed`. The same process keeps finished spans so `GET /incidents/{id}/agent-runs` can rebuild the tree.
3. **Exporters.** Spans are written as JSON log lines (CloudWatch Logs, 7-day retention) and, when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, to that OTLP endpoint for AgentCore Observability. There is no always-on collector.
4. **Metrics.** System and AI counters are emitted as CloudWatch Embedded Metric Format in namespace `AIIncidentCopilot/Observability`. `queue_age` and `dlq_messages` stay on the SQS metrics already produced by the ingest queues. A dashboard in `infra/modules/cloudwatch` graphs both.
5. **Cost API.** `GET /metrics/costs` and `GET /incidents/{id}/agent-runs` return `EstimatedCostPerIncident`, `TokensPerIncident`, `ToolCallsPerIncident`, `RuntimePerIncident`, and `RagCallsPerIncident` from stored runs. Figures are estimates, not an invoice.
6. **Redaction.** The JSON formatter drops bearer tokens, AWS access keys, full prompts, and tool secrets before a line is emitted.

## Cost impact

- Log groups for traces and embedded metrics retain data for 7 days.
- Custom metrics are emitted only when an incident is ingested or an investigation runs. No extra always-on host.
- OTLP export is off unless an endpoint is configured.

## Security impact

- `PutMetricData` is allowed only for `AIIncidentCopilot/Observability`.
- Prompts and credentials are not span attributes and are redacted if they appear in a log field.

## Review date

Revisit when AgentCore Observability is enabled in the dev account, or when evaluation scores start writing `evaluation_score`.

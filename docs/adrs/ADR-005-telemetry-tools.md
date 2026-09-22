# ADR-005 — Telemetry evidence tools

- **Status:** accepted
- **Date:** 2026-09-21
- **Deciders:** project owner

## Context

Investigation needs logs, metrics, and recent deployments, but the model must not receive a whole log group or invent a query. Demo evidence already exists on the simulator fixtures. CloudWatch is the production-shaped read path.

## Decision

1. **Three read-only tools.** `query_logs`, `query_metrics`, and `get_recent_deployments` accept a strict JSON Schema and a Pydantic model. There is no free-form query field. Unknown services, log groups, and metric names are rejected. These tools do not require approval.
2. **Allowlists.** Logs come from `/{project}/{environment}/{service}` for `payments-api`, `orders-api`, and `notifications-worker`. Metrics are only `error_rate`, `request_count`, `latency_p95`, `throttles`, `duration`, and `custom_health` in namespace `AIIncidentCopilot/Demo`. Fixture signals such as `5xx_rate` map onto those names.
3. **Caps.** Windows and result counts come from `MAX_LOG_WINDOW_MINUTES`, `MAX_LOG_RESULTS`, and `MAX_METRIC_WINDOW_MINUTES`, and cannot be configured above the dev ceilings (15 minutes, 100 rows, 60 minutes). Deployments return at most five rows inside a 72 hour lookback. Every payload is redacted and truncated to 12 KB. Calls time out (default 3 seconds) and retry at most three times, and only on throttle or timeout.
4. **Untrusted data.** Tool JSON sets `untrusted: true`. Log text is returned as data. Callers must not follow instructions embedded in messages.
5. **Where evidence lives.** The simulator seeds an in-memory store for local runs and tests. The same sink can write CloudWatch logs and custom metrics. `cloudwatch-read-tool-role` may filter the three log groups and read the demo metric namespace. It cannot write logs or metrics. Deployments are read from the existing deployments table shape or from the in-memory store.
6. **Quota.** A caller may pass how many tool calls have already been used. At `MAX_TOOL_CALLS_PER_RUN` the tool raises `COST_OR_USAGE_GUARDRAIL` and does not read further. These tools do not call a model.

## Cost impact

- Log groups retain data for `log_retention_days` (7 in `dev`). Custom metrics are emitted only when a fixture is seeded or a log filter matches.
- No always-on collector. The read role is a policy, not a running function.
- Tool calls do not spend model tokens. `MAX_TOOL_CALLS_PER_RUN` still bounds how often they can be used later.

## Security impact

- IAM is limited to `logs:FilterLogEvents`, `logs:GetLogEvents`, and `logs:DescribeLogStreams` on the demo log group ARNs, plus `cloudwatch:GetMetricStatistics` and `cloudwatch:ListMetrics` with a namespace condition. `GetMetricStatistics` does not support resource-level permissions, so that statement uses `Resource: *` only together with `cloudwatch:namespace`.
- Insights queries are not granted, so a bug cannot pass an arbitrary query string.
- Secrets and bearer tokens are redacted before the payload is returned.

## Review date

Revisit when these tools are registered on the agent gateway, or when a deployment read needs its own role.

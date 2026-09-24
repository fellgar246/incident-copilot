# ADR-006 — AgentCore Gateway registration

- **Status:** accepted
- **Date:** 2026-09-24
- **Deciders:** project owner

## Context

The agent must call typed read-only tools (`get_incident`, `query_logs`, `query_metrics`, `get_recent_deployments`) through a gateway, with a schema, a timeout, an IAM scope, and a `TOOL_CALLED` audit row. Gateway Search and Web Search stay off. Each invocation counts toward `tool_calls` and `MAX_TOOL_CALLS_PER_RUN`.

The pinned Terraform AWS provider (`~> 5.70`) has no AgentCore Gateway resource. IAM for the gateway role is declarative. Creating the Gateway itself is not.

## Decision

1. **Catalog.** The only discoverable tools are the four read-only names above. The catalog stays under ten tools. `search_runbooks` and remediation tools are not registered.
2. **IAM.** `agentcore-gateway-role` may `dynamodb:GetItem` on the incidents table and `dynamodb:Query` / `GetItem` on the deployments table. Log and metric reads reuse the existing allowlisted CloudWatch policy, attached to the gateway role. The runtime role does not gain a generic AWS SDK.
3. **Gateway resource.** Until the provider exposes Gateway, `scripts/register_gateway.py` is the only registration path. It prints the target document and refuses to run when search or web search is enabled. It does not call AWS unless `GATEWAY_APPLY=1`, and even then it only submits the four catalog tools.
4. **Audit.** Every allowlisted attempt appends `TOOL_CALLED` with `tool`, `ok`, `latency_ms`, `truncated`, and `error`. Arguments are redacted in logs and are not stored on the timeline. The log field `tool_calls` is the invocation metric.

## Cost impact

- Gateway invocations are billed. `MAX_TOOL_CALLS_PER_RUN=8` caps them per run.
- Search API and Web Search are not enabled, so those prices do not apply.

## Security impact

- The agent cannot name a tool outside the catalog and have it run.
- `get_incident` rejects any `incident_id` other than the one bound to the run.
- Tool output is schema-checked and capped at 12 KB. Secrets and the system prompt are not part of the `get_incident` document.

## Review date

Revisit when the AWS provider adds a Gateway resource, and fold `scripts/register_gateway.py` into Terraform at that point.

# Release risks

Reviewed 2026-09-26 against the controls that ship in this repository.

| Risk | Mitigation | Status |
|---|---|---|
| The agent loop spends too many tokens | `MAX_AGENT_TURNS=4`, `MAX_TOOL_CALLS_PER_RUN=8`, `MAX_SESSION_SECONDS=120` | In place |
| Logs inflate cost and context | `MAX_LOG_WINDOW_MINUTES=15`, `MAX_LOG_RESULTS=100`, 12 KB truncation | In place |
| Prompt injection from logs or runbooks | Tool output is untrusted data. Safety cases cover injection, a malicious runbook, argument escalation, remediation without approval, oversized logs, a duplicate event, and a repeated remediation | In place |
| The agent invents a cause | Diagnosis separates observed evidence, retrieved guidance, and inference. Evidence is required before a conclusion | In place |
| Unsafe remediation | Human approval, allowlist, idempotency key. Destructive actions are off. Unapproved remediate returns 403 `DENIED` | In place |
| RAG becomes expensive | Corpus stays small. `MAX_RAG_RESULTS=4`. `MAX_RAG_CALLS_PER_RUN=2`. `RAG_ENABLED` can turn retrieval off | In place |
| CloudWatch grows | `LOG_RETENTION_DAYS=7` | In place |
| AWS Budgets do not stop spend in real time | Application quotas and `AI_ENABLED` / `AGENT_INVOCATION_ENABLED` / `RAG_ENABLED` / `REMEDIATION_ENABLED` | In place |
| AgentCore APIs change | Thin adapters, ADRs, provider pin `~> 5.70`. Gateway and the vector index stay in dry-run scripts until the provider can declare them | In place |
| The portfolio only works while AWS is up | Local simulator, golden fixtures, and the offline evaluation suite do not call AWS | In place |

Open follow-ups, not blockers for this release:

- The first GitHub apply still needs a human to create the `dev` environment reviewers, the remote state bucket, and `TF_TFVARS`.
- Observed demo cost below is a list-price token estimate. Confirm it in Cost Explorer after the first live session. Checklist: [cost-explorer-review.md](../runbooks/cost-explorer-review.md).

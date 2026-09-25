# ADR-009 — Offline evaluations and quality gates

- **Status:** accepted
- **Date:** 2026-09-24
- **Deciders:** project owner

## Context

A convincing diagnosis is not a quality signal. The release decision needs a versioned dataset, repeatable scores, and gates that fail the build when the agent takes an unsafe action or drops below the agreed threshold.

## Decision

1. **Dataset.** `evals/incidents.jsonl` holds at least 20 cases across cohorts A–D (deployment regression, connection-pool exhaustion, queue backlog, false positive), including prompt injection, a malicious runbook, tool-argument escalation, remediation without approval, and a low-confidence false positive.
2. **Offline runner.** `scripts/run_evaluations.py` replays fixtures through the scripted investigator and the local tools. It does not call a model vendor. `--live` is refused unless `EVAL_LIVE=1`, and even then it stays on the offline path so a manual run cannot open an unbounded cloud bill.
3. **Profiles.** Pull requests run the small `pr` subset. Pushes to `main` run the bounded `release` subset. `workflow_dispatch` can run `full`. A large model-backed suite is not part of every commit.
4. **Gates.** `unsafe_action_rate` must be 0 and every remediation execution in the suite must require approval. Evidence recall, diagnosis accuracy, p95 turns, and a per-run cost cap are enforced from `evals/expected/gates.json`. The runner exits non-zero when any gate fails.
5. **API.** `GET /evaluations` returns the summary written to `evals/expected/last_run.json`.
6. **Runtime sample.** `EVAL_SAMPLE_RATE=0.10` scores a stable fraction of finished investigations in-process. A run that already stopped for a cost guardrail is not scored: continuous evaluation is the first thing dropped when spend protection trips.
7. **AgentCore Evaluations.** Left disabled. The offline gates already fail CI, and a hosted evaluator would add account spend without changing the pass/fail decision.

## Cost impact

Offline scripted runs stay under the profile caps in `gates.json` (USD 0.05 / 0.10 / 0.25). The published `cost_per_successful_diagnosis` is an estimate from the local token counter, not an invoice. Runtime sampling does not make an extra model call.

## Security impact

Safety cases assert that injected log text, a hostile runbook, an escalated tool argument, and a remediation without approval cannot produce `delete_resource` or an execution.

## Review date

Revisit if a hosted evaluator is enabled in an account that already has a hard application quota.

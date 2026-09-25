# Evaluations

Offline dataset and quality gates for diagnosis accuracy, groundedness, unsafe-action rate, tool-call count, and estimated cost.

```text
evals/incidents.jsonl          versioned cases (cohorts A–D plus safety cases)
evals/expected/gates.json      release thresholds and per-profile cost caps
evals/expected/last_run.json   summary served by GET /evaluations
```

The runner uses fixture tools and the scripted investigator. It does not call a model vendor.

```bash
make eval          # PR subset
make eval-full     # every case
python scripts/run_evaluations.py --profile release
```

CI runs `pr` on pull requests and `release` on `main`. A manual workflow dispatch runs `full`. The process exits non-zero when an unsafe action appears or a threshold is missed. `unsafe_action_rate` must stay at 0, and remediation in the suite must be denied without approval.

`--live` is refused unless `EVAL_LIVE=1`. That flag still stays on the offline path and inside the cost cap. Hosted AgentCore Evaluations stay off.

`EVAL_SAMPLE_RATE=0.10` scores a stable fraction of finished investigations in the API process. A run already stopped by a cost guardrail is not scored.

Cost for one successful scripted diagnosis is about USD 0.00046 (`cost_per_successful_diagnosis` in `last_run.json`). A full offline run is about USD 0.009. Profile caps in `gates.json` are USD 0.05 (PR), 0.10 (release), and 0.25 (full).

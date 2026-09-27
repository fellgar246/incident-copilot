# Cost Explorer review

Run this before another live investigation if the month is approaching USD 5, and after every demo session until the first invoice is understood. Budgets refresh a few times per day. They are not a real-time stop.

## Before you continue

- [ ] Cost Explorer is grouped by **Service** for this account and the current month.
- [ ] A second view filters the tag `project=ai-incident-copilot` and `environment=dev`.
- [ ] Bedrock, AgentCore, and Knowledge Base lines are visible on their own, not only inside "Bedrock".
- [ ] The USD 5 budget and the AI-services budget still exist (`terraform output monthly_budget_name` and `ai_budget_name`).
- [ ] SNS subscriptions for budget mail are confirmed, if emails were set.
- [ ] `AI_ENABLED`, `MAX_INCIDENTS_PER_DAY`, `MAX_AGENT_TURNS`, and `MAX_TOOL_CALLS_PER_RUN` in the API Lambda still match `.env.example`.
- [ ] No NAT Gateway, RDS, OpenSearch Serverless, or ECS service is running in this account for this project.

## If the month is over the target

Stop new AI work first (`AI_ENABLED=false` keeps read APIs up), then mitigate in this order:

1. Turn off continuous evaluations.
2. Lower the daily incident cap.
3. Lower `MAX_AGENT_TURNS`.
4. Lower tool calls and prompt context.
5. Lower the number of logs consulted.
6. Switch to a cheaper model.
7. Turn RAG off outside test sessions.
8. Come back to this checklist before the next live run.

`python scripts/estimate_cost.py` prints the same order plus the offline demo-session estimate.

## After a demo session

- [ ] Note the Cost Explorer delta for that hour next to the offline estimate (about USD 0.00046 for one scripted diagnosis).
- [ ] Record the number in the observed-cost table in the README if the invoice differs.
- [ ] Confirm DLQ depth is back to zero.

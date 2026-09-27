# Backlog after v1

These are not in the current release.

## Auth

- Cognito.
- Roles: Viewer, Operator, Approver.

## Policy and memory

- AgentCore Policy for explicit tool authorization.
- AgentCore Memory only if a real cross-session case appears. Incident state stays in DynamoDB.

## Integrations

- GitHub deployment metadata from a real repository.
- Slack, Jira, and PagerDuty.

## Shape

- A second agent for investigation, remediation, or communications, only if one agent becomes hard to evaluate.
- VPC and private connectivity. Price it first. A NAT Gateway is about USD 32 / month before data processing and would miss the USD 5 `dev` target on its own. Private endpoints have their own hourly charges. Do not add them to `dev` without a new ADR.

## Already deferred inside the provider

- Declare AgentCore Gateway in Terraform when the provider grows a resource. Until then, `scripts/register_gateway.py` is dry-run by default.
- Declare a Managed Knowledge Base when a vector store fits the monthly target. Until then, retrieval uses the local corpus index unless `KNOWLEDGE_BASE_ID` is set.

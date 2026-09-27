# Runbooks

Operational guidance `search_runbooks` retrieves during an investigation. Documents in this folder carry metadata and are part of the corpus.

Keep the corpus small. Each document should name the service, the symptom, and a safe next action. Source IDs from retrieval must remain visible on the incident detail view.

- [Account bootstrap](account-bootstrap.md) — Paid plan, MFA, budget, tags, and GitHub OIDC.
- [GitHub environment](github-environment.md) — required reviewer and repository variables for deploy.
- [Cost Explorer review](cost-explorer-review.md) — what to check before another live session.
- [Destroy dev](destroy-ephemeral.md) — tear down `dev` or an `ephemeral-*` stack.

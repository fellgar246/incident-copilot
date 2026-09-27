# Destroy the dev stack

Use this only for the portfolio `dev` account or a stack whose name starts with `ephemeral-`. The script refuses every other name.

Nothing in Terraform sets `prevent_destroy`. The dashboard bucket and the corpus bucket set `force_destroy`, so destroy can delete leftover objects. The corpus can be uploaded again with `scripts/sync_knowledge.py`.

## Dry-run

```bash
python scripts/cleanup_dev.py --environment dev
```

This prints the target and does not call Terraform.

## Local state

```bash
export DESTROY_EPHEMERAL=1
python scripts/cleanup_dev.py --environment dev --apply --confirm destroy-dev --allow-local
```

Run it from a machine that already has the local `terraform.tfstate` and AWS credentials for that account.

## GitHub

1. Confirm the `dev` environment has a required reviewer. See [github-environment.md](github-environment.md).
2. Actions → **Destroy ephemeral** → Run workflow on `main`.
3. Type `destroy-dev` in the confirm input.
4. Approve the `dev` environment when GitHub asks.

The workflow assumes `ci-deploy-role` with OIDC, then runs the same script against the remote state bucket. It does not run unless `AWS_ROLE_ARN`, `TF_STATE_BUCKET`, `TF_LOCK_TABLE`, and `TF_TFVARS` are set.

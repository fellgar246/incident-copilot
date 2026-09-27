# GitHub environment protection

Deploy and destroy wait on the GitHub environment named `dev`. Create it once:

1. Repository → Settings → Environments → New environment → `dev`.
2. Required reviewers: at least one human.
3. Deployment branches: `main` only.
4. Do not add `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY`.

Repository variables (Settings → Secrets and variables → Actions → Variables):

| Name | Value |
|---|---|
| `AWS_ROLE_ARN` | Terraform output `ci_deploy_role_arn` |
| `AWS_REGION` | `us-east-1` unless you changed it |
| `TF_STATE_BUCKET` | Remote state bucket name |
| `TF_LOCK_TABLE` | DynamoDB lock table name |
| `TF_TFVARS` | Full contents of `infra/environments/dev/terraform.tfvars` |
| `GITHUB_ORG` | Optional. The OIDC role is bound to the org you set in Terraform |

`TF_TFVARS` is not an AWS key. It is required so CI does not apply the example defaults and delete the OIDC role or the budget emails. The deploy job skips itself when any of `AWS_ROLE_ARN`, `TF_STATE_BUCKET`, `TF_LOCK_TABLE`, or `TF_TFVARS` is empty.

The workflow assumes the role with `aws-actions/configure-aws-credentials` and `role-to-assume`. The trust policy only allows `ci.yml` and `destroy-ephemeral.yml` on `main`, plus the `dev` environment subject.

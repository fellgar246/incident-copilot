# Account bootstrap checklist

Complete this once before applying business infrastructure. After MFA and the budget exist, do not use the AWS Console as a product flow.

## Paid plan and region

- [ ] Confirm the account is on the **Paid** plan. AgentCore is not Free Tier.
- [ ] Confirm AgentCore Runtime, AgentCore Gateway, and Managed Knowledge Base are available in the chosen region (`us-east-1` by default, overridable via `aws_region`).
- [ ] Review remaining AWS credits. The USD 5 / month figure is a design target, not a billing guarantee.

## Security

- [ ] Enable MFA on the root user.
- [ ] Enable MFA on IAM users that can assume admin roles.
- [ ] Never commit `.env`, `*.tfvars`, `backend.hcl`, Terraform state, or long-lived AWS access keys.

## Cost controls

- [ ] Copy `infra/environments/dev/terraform.tfvars.example` to `terraform.tfvars`.
- [ ] Set `budget_notification_emails` if you want email confirmations of SNS budget alerts.
- [ ] `terraform apply` the `dev` stack to create the USD 5 monthly budget (INFO at $1, WARNING at $3, CRITICAL at $5 actual and forecast).
- [ ] Confirm global tags on created resources: `project=ai-incident-copilot`, `environment=dev`, `owner=portfolio`.

## GitHub OIDC

Leave `enable_github_oidc = false` until the GitHub org/user is known.

- [ ] Set `enable_github_oidc = true`, `github_org`, `github_repo`, `github_environment`, and the remote state bucket and lock table.
- [ ] Apply and record output `ci_deploy_role_arn`.
- [ ] Create the GitHub environment `dev` with a required reviewer. See [github-environment.md](github-environment.md).
- [ ] Store `AWS_ROLE_ARN`, `TF_STATE_BUCKET`, `TF_LOCK_TABLE`, and `TF_TFVARS` as repository variables.
- [ ] Do not store `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` in GitHub.

`ci-deploy-role` can manage this stack. It cannot create IAM users or access keys. A job must use the `dev` environment, and the workflow file must be `ci.yml` or `destroy-ephemeral.yml` on `main`.

## State

Local state is the default so `terraform validate` works without a bucket. Before anyone else applies this stack, migrate to S3 + DynamoDB using `backend.hcl.example`.

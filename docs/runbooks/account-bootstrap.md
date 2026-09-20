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

## GitHub OIDC skeleton

Leave `enable_github_oidc = false` until the GitHub org/user is known.

- [ ] Set `enable_github_oidc = true`, `github_org`, and `github_repo`.
- [ ] Apply and record output `ci_deploy_role_arn`.
- [ ] In GitHub, store `AWS_ROLE_ARN` as a repository variable. Workflows must use `aws-actions/configure-aws-credentials` with `role-to-assume`.
- [ ] Do not store `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` in GitHub.

Deploy permissions on `ci-deploy-role` are limited to `sts:GetCallerIdentity` in this bootstrap. Widen them later with least privilege.

## State

Local state is the default so `terraform validate` works without a bucket. Before anyone else applies this stack, migrate to S3 + DynamoDB using `backend.hcl.example`.

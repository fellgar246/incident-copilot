output "github_oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider, if enabled."
  value       = try(aws_iam_openid_connect_provider.github[0].arn, null)
}

output "ci_deploy_role_arn" {
  description = "ARN of the CI deploy role skeleton, if enabled."
  value       = try(aws_iam_role.ci_deploy[0].arn, null)
}

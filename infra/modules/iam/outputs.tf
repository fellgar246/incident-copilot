output "github_oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider, if enabled."
  value       = try(aws_iam_openid_connect_provider.github[0].arn, null)
}

output "ci_deploy_role_arn" {
  description = "ARN of the CI deploy role skeleton, if enabled."
  value       = try(aws_iam_role.ci_deploy[0].arn, null)
}

output "investigation_worker_role_arn" {
  description = "ARN of investigation-worker-role."
  value       = aws_iam_role.investigation_worker.arn
}

output "investigation_worker_role_name" {
  description = "Name of investigation-worker-role."
  value       = aws_iam_role.investigation_worker.name
}

output "cloudwatch_read_tool_role_arn" {
  description = "ARN of cloudwatch-read-tool-role."
  value       = aws_iam_role.cloudwatch_read_tool.arn
}

output "agentcore_runtime_role_arn" {
  description = "ARN of agentcore-runtime-role."
  value       = aws_iam_role.agentcore_runtime.arn
}

output "agentcore_runtime_role_name" {
  description = "Name of agentcore-runtime-role."
  value       = aws_iam_role.agentcore_runtime.name
}

output "agentcore_gateway_role_arn" {
  description = "ARN of agentcore-gateway-role."
  value       = aws_iam_role.agentcore_gateway.arn
}

output "agentcore_gateway_role_name" {
  description = "Name of agentcore-gateway-role."
  value       = aws_iam_role.agentcore_gateway.name
}

output "cloudwatch_read_tool_role_name" {
  description = "Name of cloudwatch-read-tool-role."
  value       = aws_iam_role.cloudwatch_read_tool.name
}

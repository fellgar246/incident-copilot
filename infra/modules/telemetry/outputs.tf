output "metric_namespace" {
  description = "Namespace for demo custom metrics."
  value       = var.metric_namespace
}

output "log_group_names" {
  description = "Allowlisted demo log groups, keyed by service."
  value       = { for key, group in aws_cloudwatch_log_group.demo : key => group.name }
}

output "cloudwatch_read_tool_role_name" {
  description = "Role that received the read-only telemetry policy."
  value       = var.cloudwatch_read_tool_role_name
}

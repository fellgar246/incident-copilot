output "trace_log_group_name" {
  description = "Log group that stores agent trace lines."
  value       = aws_cloudwatch_log_group.traces.name
}

output "metric_log_group_name" {
  description = "Log group that stores embedded metric lines."
  value       = aws_cloudwatch_log_group.metrics.name
}

output "metric_namespace" {
  description = "Namespace used by the cost and trace dashboard."
  value       = var.metric_namespace
}

output "log_retention_days" {
  description = "Retention applied to the observability log groups."
  value       = var.log_retention_days
}

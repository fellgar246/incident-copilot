output "dashboard_name" {
  description = "CloudWatch dashboard for agent traces and cost metrics."
  value       = aws_cloudwatch_dashboard.agent.dashboard_name
}

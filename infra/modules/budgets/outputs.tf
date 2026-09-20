output "budget_name" {
  description = "Name of the account-wide monthly cost budget."
  value       = aws_budgets_budget.monthly.name
}

output "ai_budget_name" {
  description = "Name of the optional Bedrock-filtered budget, if created."
  value       = try(aws_budgets_budget.ai_services[0].name, null)
}

output "sns_topic_arn" {
  description = "SNS topic that receives budget notifications."
  value       = aws_sns_topic.budget_alerts.arn
}

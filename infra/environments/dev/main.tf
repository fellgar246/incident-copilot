module "budgets" {
  source = "../../modules/budgets"

  project                   = var.project
  environment               = var.environment
  monthly_budget_usd        = var.monthly_budget_usd
  notification_emails       = var.budget_notification_emails
  create_ai_services_budget = true
}

module "iam" {
  source = "../../modules/iam"

  project            = var.project
  environment        = var.environment
  enable_github_oidc = var.enable_github_oidc
  github_org         = var.github_org
  github_repo        = var.github_repo
}

output "aws_region" {
  value = var.aws_region
}

output "log_retention_days" {
  value = var.log_retention_days
}

output "max_incidents_per_day" {
  value = var.max_incidents_per_day
}

output "knowledge_corpus_enabled" {
  value = var.knowledge_corpus_enabled
}

output "ai_enabled" {
  value = var.ai_enabled
}

output "monthly_budget_name" {
  value = module.budgets.budget_name
}

output "ai_budget_name" {
  value = module.budgets.ai_budget_name
}

output "budget_sns_topic_arn" {
  value = module.budgets.sns_topic_arn
}

output "github_oidc_provider_arn" {
  value = module.iam.github_oidc_provider_arn
}

output "ci_deploy_role_arn" {
  value = module.iam.ci_deploy_role_arn
}

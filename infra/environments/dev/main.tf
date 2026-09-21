module "budgets" {
  source = "../../modules/budgets"

  project                   = var.project
  environment               = var.environment
  owner                     = var.owner
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

module "dynamodb" {
  source = "../../modules/dynamodb"

  project            = var.project
  environment        = var.environment
  log_retention_days = var.log_retention_days
}

module "api" {
  source = "../../modules/api"

  project                = var.project
  environment            = var.environment
  aws_region             = var.aws_region
  lambda_source_dir      = abspath("${path.module}/../../../apps/api/src")
  incidents_table_name   = module.dynamodb.incidents_table_name
  incidents_table_arn    = module.dynamodb.incidents_table_arn
  deployments_table_name = module.dynamodb.deployments_table_name
  deployments_table_arn  = module.dynamodb.deployments_table_arn
  log_retention_days     = var.log_retention_days
  ai_enabled             = var.ai_enabled
  max_incidents_per_day  = var.max_incidents_per_day
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

output "incidents_table_name" {
  value = module.dynamodb.incidents_table_name
}

output "deployments_table_name" {
  value = module.dynamodb.deployments_table_name
}

output "api_endpoint" {
  value = module.api.api_endpoint
}

output "api_role_arn" {
  value = module.api.api_role_arn
}

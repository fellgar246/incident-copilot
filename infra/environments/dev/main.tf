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

  project               = var.project
  environment           = var.environment
  aws_region            = var.aws_region
  enable_github_oidc    = var.enable_github_oidc
  github_org            = var.github_org
  github_repo           = var.github_repo
  incidents_table_arn   = module.dynamodb.incidents_table_arn
  deployments_table_arn = module.dynamodb.deployments_table_arn
}

module "dynamodb" {
  source = "../../modules/dynamodb"

  project            = var.project
  environment        = var.environment
  log_retention_days = var.log_retention_days
}

module "events" {
  source = "../../modules/events"

  project                        = var.project
  environment                    = var.environment
  aws_region                     = var.aws_region
  lambda_source_dir              = abspath("${path.module}/../../../services/incident-worker/src")
  investigation_worker_role_arn  = module.iam.investigation_worker_role_arn
  investigation_worker_role_name = module.iam.investigation_worker_role_name
  incidents_table_name           = module.dynamodb.incidents_table_name
  incidents_table_arn            = module.dynamodb.incidents_table_arn
  deployments_table_name         = module.dynamodb.deployments_table_name
  log_retention_days             = var.log_retention_days
  ai_enabled                     = var.ai_enabled
  max_incidents_per_day          = var.max_incidents_per_day
}

module "telemetry" {
  source = "../../modules/telemetry"

  project                        = var.project
  environment                    = var.environment
  log_retention_days             = var.log_retention_days
  cloudwatch_read_tool_role_name = module.iam.cloudwatch_read_tool_role_name
  gateway_role_name              = module.iam.agentcore_gateway_role_name
}

module "knowledge_base" {
  source = "../../modules/knowledge-base"
  count  = var.knowledge_corpus_enabled ? 1 : 0

  project     = var.project
  environment = var.environment
  aws_region  = var.aws_region
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
  event_bus_name         = module.events.event_bus_name
  event_bus_arn          = module.events.event_bus_arn
  event_source           = module.events.event_source
}

module "observability" {
  source = "../../modules/observability"

  project            = var.project
  environment        = var.environment
  log_retention_days = var.log_retention_days
  api_role_name      = module.api.api_role_name
  worker_role_name   = module.iam.investigation_worker_role_name
}

module "cloudwatch" {
  source = "../../modules/cloudwatch"

  project           = var.project
  environment       = var.environment
  aws_region        = var.aws_region
  metric_namespace  = module.observability.metric_namespace
  ingest_queue_name = module.events.queue_name
  dlq_name          = module.events.dlq_name
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

output "investigation_worker_role_arn" {
  value = module.iam.investigation_worker_role_arn
}

output "event_bus_name" {
  value = module.events.event_bus_name
}

output "event_source" {
  value = module.events.event_source
}

output "ingest_queue_url" {
  value = module.events.queue_url
}

output "ingest_dlq_url" {
  value = module.events.dlq_url
}

output "worker_function_name" {
  value = module.events.worker_function_name
}

output "dlq_messages_alarm_name" {
  value = module.events.dlq_messages_alarm_name
}

output "agentcore_runtime_role_arn" {
  value = module.iam.agentcore_runtime_role_arn
}

output "cloudwatch_read_tool_role_arn" {
  value = module.iam.cloudwatch_read_tool_role_arn
}

output "agentcore_gateway_role_arn" {
  value = module.iam.agentcore_gateway_role_arn
}

output "knowledge_bucket_name" {
  value = try(module.knowledge_base[0].bucket_name, null)
}

output "knowledge_tool_role_arn" {
  value = try(module.knowledge_base[0].knowledge_tool_role_arn, null)
}

output "metric_namespace" {
  value = module.telemetry.metric_namespace
}

output "demo_log_group_names" {
  value = module.telemetry.log_group_names
}

output "trace_log_group_name" {
  value = module.observability.trace_log_group_name
}

output "observability_dashboard_name" {
  value = module.cloudwatch.dashboard_name
}

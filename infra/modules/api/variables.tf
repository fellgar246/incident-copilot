variable "project" {
  type        = string
  description = "Project tag and name prefix."
}

variable "environment" {
  type        = string
  description = "Environment name (dev)."
}

variable "aws_region" {
  type        = string
  description = "AWS region injected into the Lambda environment."
}

variable "lambda_source_dir" {
  type        = string
  description = "Directory zipped as the API Lambda. Must contain the api Python package."
}

variable "incidents_table_name" {
  type        = string
  description = "DynamoDB incidents table name."
}

variable "incidents_table_arn" {
  type        = string
  description = "DynamoDB incidents table ARN."
}

variable "deployments_table_name" {
  type        = string
  description = "DynamoDB deployments table name."
}

variable "deployments_table_arn" {
  type        = string
  description = "DynamoDB deployments table ARN."
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention and application TTL, in days."
  default     = 7
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "API Lambda timeout."
  default     = 10
}

variable "lambda_memory_mb" {
  type        = number
  description = "API Lambda memory. Keep low to limit cost."
  default     = 256
}

variable "reserved_concurrent_executions" {
  type        = number
  description = "Cap concurrent API Lambdas in this environment."
  default     = 5
}

variable "ai_enabled" {
  type        = bool
  description = "AI circuit breaker mirrored into the Lambda environment."
  default     = true
}

variable "agent_invocation_enabled" {
  type    = bool
  default = true
}

variable "rag_enabled" {
  type    = bool
  default = true
}

variable "remediation_enabled" {
  type    = bool
  default = true
}

variable "target_monthly_cost_usd" {
  type    = string
  default = "5.00"
}

variable "max_incidents_per_day" {
  type    = number
  default = 10
}

variable "max_agent_runs_per_incident" {
  type    = number
  default = 2
}

variable "max_agent_turns" {
  type    = number
  default = 4
}

variable "max_tool_calls_per_run" {
  type    = number
  default = 8
}

variable "max_rag_calls_per_run" {
  type    = number
  default = 2
}

variable "max_rag_results" {
  type    = number
  default = 4
}

variable "max_log_window_minutes" {
  type    = number
  default = 15
}

variable "max_log_results" {
  type    = number
  default = 100
}

variable "max_metric_window_minutes" {
  type    = number
  default = 60
}

variable "max_session_seconds" {
  type    = number
  default = 120
}

variable "max_model_input_tokens_per_call" {
  type    = number
  default = 6000
}

variable "max_model_output_tokens_per_call" {
  type    = number
  default = 1200
}

variable "eval_sample_rate" {
  type    = string
  default = "0.10"
}

variable "cors_origins" {
  type        = string
  description = "Comma-separated CORS origins for the API."
  default     = "http://localhost:3000"
}

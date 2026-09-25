variable "project" {
  type        = string
  description = "Project tag and name prefix."
}

variable "environment" {
  type        = string
  description = "Environment name (dev)."
}

variable "log_retention_days" {
  type        = number
  description = "Retention for trace and metric log groups. Dev uses 7 days."
  default     = 7

  validation {
    condition     = var.log_retention_days >= 1 && var.log_retention_days <= 7
    error_message = "log_retention_days must be between 1 and 7."
  }
}

variable "metric_namespace" {
  type        = string
  description = "CloudWatch namespace for agent and system metrics."
  default     = "AIIncidentCopilot/Observability"
}

variable "api_role_name" {
  type        = string
  description = "api-role that may publish the observability namespace."
}

variable "worker_role_name" {
  type        = string
  description = "investigation-worker-role that may publish the observability namespace."
}

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
  description = "Retention for demo service log groups."
}

variable "metric_namespace" {
  type        = string
  description = "CloudWatch namespace for demo custom metrics."
  default     = "AIIncidentCopilot/Demo"
}

variable "cloudwatch_read_tool_role_name" {
  type        = string
  description = "Name of cloudwatch-read-tool-role. The read policy is attached here."
}

variable "demo_services" {
  type        = list(string)
  description = "Demo services that receive a log group. Must match the tool allowlist."
  default     = ["payments-api", "orders-api", "notifications-worker"]

  validation {
    condition     = length(var.demo_services) > 0
    error_message = "demo_services must list at least one service."
  }
}

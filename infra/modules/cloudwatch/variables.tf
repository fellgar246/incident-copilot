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
  description = "Region shown on the dashboard."
}

variable "metric_namespace" {
  type        = string
  description = "Custom metric namespace for agent and system series."
}

variable "ingest_queue_name" {
  type        = string
  description = "SQS queue whose age is the queue_age series."
}

variable "dlq_name" {
  type        = string
  description = "SQS DLQ whose visible depth is the dlq_messages series."
}

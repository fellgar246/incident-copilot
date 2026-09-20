variable "aws_region" {
  type        = string
  description = "AWS region. Must support Bedrock AgentCore before later slices."
  default     = "us-east-1"
}

variable "project" {
  type        = string
  description = "Project tag and name prefix."
  default     = "ai-incident-copilot"
}

variable "environment" {
  type        = string
  description = "Environment name."
  default     = "dev"
}

variable "owner" {
  type        = string
  description = "Owner tag applied to every tagged resource."
  default     = "portfolio"
}

variable "monthly_budget_usd" {
  type        = number
  description = "Monthly cost target used as the AWS Budget limit."
  default     = 5
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention used by later modules."
  default     = 7
}

variable "max_incidents_per_day" {
  type        = number
  description = "Application quota mirrored into infrastructure outputs."
  default     = 10
}

variable "knowledge_corpus_enabled" {
  type        = bool
  description = "Whether the knowledge corpus path is enabled for later slices."
  default     = true
}

variable "ai_enabled" {
  type        = bool
  description = "Global AI circuit breaker mirrored from application config."
  default     = true
}

variable "budget_notification_emails" {
  type        = list(string)
  description = "Emails that must confirm an SNS subscription to receive budget alerts."
  default     = []
}

variable "enable_github_oidc" {
  type        = bool
  description = "Create GitHub OIDC provider and CI role skeleton."
  default     = false
}

variable "github_org" {
  type        = string
  description = "GitHub org or user allowed to assume the CI role."
  default     = ""
}

variable "github_repo" {
  type        = string
  description = "GitHub repository name allowed to assume the CI role."
  default     = "ai-incident-copilot"
}

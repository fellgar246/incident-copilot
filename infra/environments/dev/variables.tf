variable "aws_region" {
  type        = string
  description = "AWS region. Must support Bedrock AgentCore before later slices."
  default     = "us-east-1"

  validation {
    condition     = length(var.aws_region) > 0
    error_message = "aws_region must be a non-empty region id such as us-east-1."
  }
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

  validation {
    condition     = var.monthly_budget_usd > 0
    error_message = "monthly_budget_usd must be greater than zero."
  }
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention used by later modules."
  default     = 7

  validation {
    condition     = var.log_retention_days >= 1
    error_message = "log_retention_days must be at least 1."
  }
}

variable "max_incidents_per_day" {
  type        = number
  description = "Application quota mirrored into infrastructure outputs."
  default     = 10

  validation {
    condition     = var.max_incidents_per_day >= 0
    error_message = "max_incidents_per_day must be >= 0."
  }
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
  description = "Create the GitHub OIDC provider and ci-deploy-role."
  default     = false
}

variable "github_environment" {
  type        = string
  description = "GitHub environment whose jobs may assume ci-deploy-role."
  default     = "dev"
}

variable "terraform_state_bucket" {
  type        = string
  description = "Optional remote state bucket granted to ci-deploy-role."
  default     = ""
}

variable "terraform_lock_table" {
  type        = string
  description = "Optional DynamoDB lock table granted to ci-deploy-role."
  default     = ""
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

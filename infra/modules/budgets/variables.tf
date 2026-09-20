variable "project" {
  type        = string
  description = "Project tag and name prefix."
}

variable "environment" {
  type        = string
  description = "Environment name (dev)."
}

variable "owner" {
  type        = string
  description = "Owner tag applied to tagged resources in this module."
}

variable "monthly_budget_usd" {
  type        = number
  description = "Monthly cost target used as the AWS Budget limit."
}

variable "notification_emails" {
  type        = list(string)
  description = "Optional email subscribers for budget alerts. Leave empty to use SNS only."
  default     = []
}

variable "create_ai_services_budget" {
  type        = bool
  description = "Create a second budget filtered to Bedrock-related services."
  default     = true
}

variable "ai_budget_service_names" {
  type        = list(string)
  description = "Cost Explorer service names included in the optional AI budget. AgentCore usage is billed under Amazon Bedrock."
  default     = ["Amazon Bedrock"]
}

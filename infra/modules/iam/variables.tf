variable "project" {
  type        = string
  description = "Project tag and name prefix."
}

variable "environment" {
  type        = string
  description = "Environment name (dev)."
}

variable "enable_github_oidc" {
  type        = bool
  description = "Create the GitHub OIDC provider and CI deploy role skeleton."
  default     = false
}

variable "github_org" {
  type        = string
  description = "GitHub organization or user that is allowed to assume the CI role."
  default     = ""
}

variable "github_repo" {
  type        = string
  description = "Repository name allowed to assume the CI role."
  default     = "ai-incident-copilot"
}

variable "aws_region" {
  type        = string
  description = "Region used in the runtime role's model ARN."
  default     = "us-east-1"
}

variable "incidents_table_arn" {
  type        = string
  description = "Incidents table the runtime may read and write."
  default     = ""
}

variable "deployments_table_arn" {
  type        = string
  description = "Deployments table the runtime may read."
  default     = ""
}

variable "bedrock_model_id" {
  type        = string
  description = "Foundation model the runtime may invoke."
  default     = "amazon.nova-micro-v1:0"
}

variable "github_oidc_thumbprints" {
  type        = list(string)
  description = "GitHub Actions OIDC thumbprints. AWS still requires at least one value."
  default     = ["d89e3bd43d5d909b47a18977aa9d5ce36cee184c"]
}

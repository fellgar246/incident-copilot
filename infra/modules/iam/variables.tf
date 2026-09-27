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
  description = "Create the GitHub OIDC provider and ci-deploy-role."
  default     = false
}

variable "github_environment" {
  type        = string
  description = "GitHub environment allowed to assume ci-deploy-role for apply and destroy."
  default     = "dev"
}

variable "github_workflows" {
  type        = list(string)
  description = "Workflow filenames on main that may assume ci-deploy-role."
  default     = ["ci.yml", "destroy-ephemeral.yml"]
}

variable "terraform_state_bucket" {
  type        = string
  description = "Remote state bucket the CI role may read and write. Empty skips that grant."
  default     = ""
}

variable "terraform_lock_table" {
  type        = string
  description = "DynamoDB lock table the CI role may use. Empty skips that grant."
  default     = ""
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

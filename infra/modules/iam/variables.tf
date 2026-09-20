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

variable "github_oidc_thumbprints" {
  type        = list(string)
  description = "GitHub Actions OIDC thumbprints. AWS still requires at least one value."
  default     = ["d89e3bd43d5d909b47a18977aa9d5ce36cee184c"]
}

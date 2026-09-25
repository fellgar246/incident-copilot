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

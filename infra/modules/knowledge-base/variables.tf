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
  description = "Region for the knowledge-base retrieve ARN."
  default     = "us-east-1"
}

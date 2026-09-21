terraform {
  required_version = ">= 1.6.0"

  # Local state is the bootstrap default so `terraform validate` works without
  # a remote bucket. Move to S3 + DynamoDB lock before shared environments.
  backend "local" {
    path = "terraform.tfstate"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.6"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      project     = var.project
      environment = var.environment
      owner       = var.owner
    }
  }
}

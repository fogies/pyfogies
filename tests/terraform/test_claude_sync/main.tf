terraform {
  required_version = "~> 1.15"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.37"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = var.tags
  }
}

variable "region" {
  description = "AWS region in which to create the claude-sync bucket."
  type        = string
}

variable "name" {
  description = "Base name for claude-sync resources."
  type        = string
}

variable "tags" {
  description = "Tags to apply to created resources."
  type        = map(string)
  default     = {}
}

module "claude_sync" {
  source = "../../../terraform/claude_sync"

  name = var.name
}

output "bucket" {
  description = "Name of the S3 bucket claude-sync stores to."
  value       = module.claude_sync.bucket
}

output "region" {
  description = "Region of the S3 bucket."
  value       = module.claude_sync.region
}

output "user_name" {
  description = "Name of the IAM user claude-sync signs in as."
  value       = module.claude_sync.user_name
}

terraform {
  required_version = "~> 1.14.0"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  description = "AWS region in which to create ECR resources."
  type        = string
}

module "ecr" {
  source = "../../../terraform/ecr"

  region                     = var.region
  repositories               = ["pyfogies-test-ecr-a", "pyfogies-test-ecr-b"]
  lifecycle_keep_count_limit = 10
  lifecycle_keep_days_limit  = 180
  force_delete               = true
}

output "ecr" {
  description = "Entire ECR module output."
  value       = module.ecr
}

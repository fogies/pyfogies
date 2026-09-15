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
  description = "AWS region in which to create resources."
  type        = string
}

variable "log_group_name" {
  description = "Name of the CloudWatch log group."
  type        = string
}

variable "retention_in_days" {
  description = "Number of days to retain log events."
  type        = number
}

module "cloudwatch" {
  source = "../../../terraform/cloudwatch"

  name              = var.log_group_name
  retention_in_days = var.retention_in_days
}

output "cloudwatch" {
  description = "Entire cloudwatch module output."
  value       = module.cloudwatch
}

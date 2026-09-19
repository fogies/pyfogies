terraform {
  required_version = "~> 1.15"

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
  description = "AWS region."
  type        = string
}

variable "username" {
  description = "Name of the IAM user to grant permissions to."
  type        = string
}

module "access_key_permissions" {
  source = "../../../terraform/access_key_permissions"

  username = var.username
  name     = "test"
  statements = [
    {
      effect = "Allow"
      actions = [
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeRegions",
        "ec2:DescribeVpcs",
      ]
      resources = ["*"]
    }
  ]
}

output "access_key_permissions" {
  description = "Entire access-key-permissions module output."
  value       = module.access_key_permissions
}

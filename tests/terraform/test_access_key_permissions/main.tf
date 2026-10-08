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

variable "policies" {
  description = "Managed policy ARNs to attach."
  type        = list(string)
  default     = []
}

variable "statements" {
  description = "Policy statements to grant."
  type = list(object({
    effect    = string
    actions   = list(string)
    resources = list(string)
  }))
  default = []
}

module "access_key_permissions" {
  source = "../../../terraform/access_key_permissions"

  username   = var.username
  policies   = var.policies
  statements = var.statements
}

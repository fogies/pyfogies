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
  description = "AWS region in which to create network resources."
  type        = string
}

variable "tags" {
  description = "Tags to apply to created resources."
  type        = map(string)
  default     = {}
}

module "network" {
  source = "../../../terraform/network"

  region                  = var.region
  availability_zone_count = 2
  tags                    = var.tags
}

output "network" {
  description = "Entire network module output."
  value       = module.network
}

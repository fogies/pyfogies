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

  default_tags {
    tags = var.tags
  }
}

variable "backend_name" {
  description = "Base prefix for backend resources."
  type        = string
}

variable "region" {
  description = "AWS region in which to create backend resources."
  type        = string
}

variable "state_names" {
  description = "Names of Terraform states to manage within this backend."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to backend resources."
  type        = map(string)
  default     = {}
}

module "backend" {
  source = "../../../../terraform/backend"

  backend_name = var.backend_name
  state_names  = var.state_names
}

output "backend" {
  description = "Entire backend module output."
  value       = module.backend
}

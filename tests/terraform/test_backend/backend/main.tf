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

variable "name" {
  description = "Base prefix for backend resources."
  type        = string
}

variable "region" {
  description = "AWS region in which to create backend resources."
  type        = string
}

variable "states" {
  description = "Logical names of Terraform states to manage within this backend."
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

  name   = var.name
  region = var.region
  states = var.states
  tags   = var.tags
}

output "backend" {
  description = "Entire backend module output."
  value       = module.backend
}

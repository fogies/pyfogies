terraform {
  required_version = "~> 1.14.0"

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

variable "force_destroy" {
  description = "Whether to allow force destruction of the S3 bucket."
  type        = bool
  default     = false
}

module "backend" {
  source = "../../../terraform/backend"

  name          = var.name
  region        = var.region
  states        = var.states
  tags          = var.tags
  force_destroy = var.force_destroy
}

output "backend" {
  description = "Entire backend module output."
  value       = module.backend
}

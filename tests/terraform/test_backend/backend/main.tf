terraform {
  required_version = "~> 1.14.0"

  backend "s3" {
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.backend.region
}

variable "backend" {
  description = "Backend configuration."
  type = object({
    name          = string
    region        = string
    states        = list(string)
    tags          = map(string)
    force_destroy = bool
  })
}

module "backend" {
  source = "../../../../terraform/backend"

  name          = var.backend.name
  region        = var.backend.region
  states        = var.backend.states
  tags          = var.backend.tags
  force_destroy = var.backend.force_destroy
}

output "backend" {
  description = "Entire backend module output."
  value       = module.backend
}

terraform {
  required_version = "~> 1.14.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "backend" {
  description = "Backend configuration."
  type = object({
    name          = string
    states        = list(string)
    tags          = map(string)
    force_destroy = bool
  })
}

module "backend" {
  source = "../../../../terraform/backend"

  name          = var.backend.name
  states        = var.backend.states
  tags          = var.backend.tags
  force_destroy = var.backend.force_destroy
}

output "backend" {
  description = "Entire backend module output."
  value       = module.backend
}

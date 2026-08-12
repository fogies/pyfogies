terraform {
  required_version = "~> 1.14.0"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
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

variable "alb_name" {
  description = "Name of the ALB."
  type        = string
}

module "network" {
  source = "../../../../terraform/network"

  region                  = var.region
  availability_zone_count = 2
}

module "alb" {
  source = "../../../../terraform/alb"

  region                  = var.region
  name                    = var.alb_name
  subnet_ids              = module.network.subnet_ids
  security_group_ids      = module.network.security_group_ids
  self_signed_certificate = true
}

output "network" {
  description = "Network module output."
  value       = module.network
}

output "alb" {
  description = "ALB module output."
  value       = module.alb
}

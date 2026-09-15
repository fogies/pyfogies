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

variable "hosted_zone_name" {
  description = "Route 53 hosted zone name."
  type        = string
}

variable "alb_dns_name" {
  description = "DNS name of the existing ALB."
  type        = string
}

variable "alb_zone_id" {
  description = "Hosted zone ID of the existing ALB."
  type        = string
}

variable "listener_https_arn" {
  description = "ARN of the existing ALB HTTPS listener."
  type        = string
}

module "alb_dns" {
  source = "../../../terraform/alb_dns"

  hosted_zone_name = var.hosted_zone_name
  hostnames = [
    "test-alb-dns.${var.hosted_zone_name}",
    "test-alb-dns-1.${var.hosted_zone_name}",
    "test-alb-dns-2.${var.hosted_zone_name}",
    "test-alb-dns-3.${var.hosted_zone_name}",
  ]
  alb_dns_name       = var.alb_dns_name
  alb_zone_id        = var.alb_zone_id
  listener_https_arn = var.listener_https_arn
}

output "hostname" {
  description = "Primary hostname at which the ALB is reachable via DNS."
  value       = module.alb_dns.hostname
}

output "hostnames" {
  description = "All hostnames at which the ALB is reachable via DNS."
  value       = module.alb_dns.hostnames
}

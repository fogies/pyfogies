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
  description = "AWS region in which to create the ACM certificate."
  type        = string
}

variable "zone_name" {
  description = "Route 53 hosted zone name in which to create DNS validation records."
  type        = string
}

variable "domains" {
  description = "Domain names to include on the certificate."
  type        = list(string)
}

module "certificate" {
  source = "../../../terraform/certificate"

  region    = var.region
  zone_name = var.zone_name
  domains   = var.domains
}

output "certificate" {
  description = "Certificate module output."
  value       = module.certificate
}

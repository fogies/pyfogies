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

variable "alb_name" {
  description = "Name of the ALB."
  type        = string
}

variable "zone_name" {
  description = "Route 53 hosted zone name. Used to create the DNS-validated certificate and ALB alias record."
  type        = string
}

data "aws_route53_zone" "zone" {
  name = var.zone_name
}

resource "aws_acm_certificate" "cert" {
  domain_name       = "*.${var.zone_name}"
  validation_method = "DNS"
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.cert.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id = data.aws_route53_zone.zone.zone_id
  name    = each.value.name
  type    = each.value.type
  records = [each.value.record]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "cert" {
  certificate_arn         = aws_acm_certificate.cert.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

module "network" {
  source = "../../../../terraform/network"

  region                  = var.region
  availability_zone_count = 2
}

module "alb" {
  source = "../../../../terraform/alb"

  region             = var.region
  name               = var.alb_name
  subnet_ids         = module.network.subnet_ids
  security_group_ids = module.network.security_group_ids
  certificate_arn    = aws_acm_certificate_validation.cert.certificate_arn
}

resource "aws_route53_record" "alb" {
  zone_id = data.aws_route53_zone.zone.zone_id
  name    = "test-alb.${var.zone_name}"
  type    = "A"

  alias {
    name                   = module.alb.alb_dns_name
    zone_id                = module.alb.alb_zone_id
    evaluate_target_health = true
  }
}

output "network" {
  description = "Network module output."
  value       = module.network
}

output "alb" {
  description = "ALB module output."
  value       = module.alb
}

output "alb_hostname" {
  description = "Hostname at which the ALB is reachable via DNS."
  value       = "test-alb.${var.zone_name}"
}

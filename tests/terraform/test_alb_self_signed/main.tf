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

variable "vpc_id" {
  description = "VPC ID in which to create resources."
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs in which to place the ALB."
  type        = set(string)
}

module "alb_sg" {
  source = "../../../terraform/security_group/alb_public_http_https"

  name   = var.alb_name
  vpc_id = var.vpc_id
}

module "alb" {
  source = "../../../terraform/alb"

  region                  = var.region
  name                    = var.alb_name
  subnet_ids              = var.subnet_ids
  security_group_ids      = [module.alb_sg.security_group_id]
  self_signed_certificate = true
}

output "alb_security_group_id" {
  description = "ID of the ALB security group."
  value       = module.alb_sg.security_group_id
}

output "alb" {
  description = "ALB module output."
  value       = module.alb
}

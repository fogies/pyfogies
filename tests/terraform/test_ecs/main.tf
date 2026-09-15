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

variable "name" {
  description = "Base name for resources."
  type        = string
}

variable "vpc_id" {
  description = "VPC in which to place the ECS service."
  type        = string
}

variable "subnet_ids" {
  description = "Subnets in which to run ECS tasks."
  type        = set(string)
}

variable "alb_security_group_id" {
  description = "ID of the ALB security group. ECS tasks will allow inbound from it on the container port."
  type        = string
}

variable "listener_https_arn" {
  description = "ARN of the HTTPS listener on the shared ALB."
  type        = string
}

module "ecs_sg" {
  source = "../../../terraform/security_group/ecs_from_alb_http"

  name                  = var.name
  vpc_id                = var.vpc_id
  alb_security_group_id = var.alb_security_group_id
}

module "cloudwatch" {
  source = "../../../terraform/cloudwatch"

  name              = "/ecs/${var.name}"
  retention_in_days = 7
}

module "ecs" {
  source = "../../../terraform/ecs"

  region                 = var.region
  name                   = var.name
  vpc_id                 = var.vpc_id
  subnet_ids             = var.subnet_ids
  security_group_ids     = [module.ecs_sg.security_group_id]
  listener_https_arn     = var.listener_https_arn
  log_group_name         = module.cloudwatch.log_group_name
  image                  = "public.ecr.aws/nginx/nginx:stable-alpine"
  listener_rule_priority = 100
  container_port         = 80
  cpu                    = 256
  memory                 = 512
  desired_count          = 1
  deregistration_delay   = 15 # Low for fast teardown; production default is 300s.
  stop_timeout           = 5  # Low for fast teardown; production default is 30s.
}

output "cloudwatch" {
  description = "CloudWatch module output."
  value       = module.cloudwatch
}

output "ecs" {
  description = "ECS module output."
  value       = module.ecs
}

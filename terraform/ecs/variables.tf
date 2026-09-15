variable "region" {
  description = "AWS region in which to create ECS resources."
  type        = string
}

variable "name" {
  description = "Base name for ECS resources (cluster, service, task definition, IAM roles)."
  type        = string

  validation {
    condition     = length(var.name) <= 32
    error_message = "name must be at most 32 characters (ALB target group name limit)."
  }
}

variable "vpc_id" {
  description = "VPC ID in which to run ECS tasks."
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs in which to run ECS tasks."
  type        = set(string)
}

variable "security_group_ids" {
  description = "Security group IDs to attach to ECS tasks."
  type        = set(string)
}

variable "listener_https_arn" {
  description = "ARN of the ALB HTTPS listener to attach the ECS service to."
  type        = string
}

variable "listener_rule_priority" {
  description = "Priority for the ALB listener rule (1-50000). Lower values have higher priority."
  type        = number

  validation {
    condition     = var.listener_rule_priority >= 1 && var.listener_rule_priority <= 50000
    error_message = "listener_rule_priority must be between 1 and 50000."
  }
}

variable "log_group_name" {
  description = "CloudWatch log group name for container logs. When null, logging is not configured."
  type        = string
  nullable    = true
}

variable "image" {
  description = "Docker image URI to run in the ECS task (e.g. public.ecr.aws/nginx/nginx:stable-alpine)."
  type        = string
}

variable "container_port" {
  description = "Port the container listens on."
  type        = number
}

variable "cpu" {
  description = "Fargate task CPU units (256, 512, 1024, 2048, or 4096)."
  type        = number

  validation {
    condition     = contains([256, 512, 1024, 2048, 4096], var.cpu)
    error_message = "cpu must be one of 256, 512, 1024, 2048, or 4096."
  }
}

variable "memory" {
  description = "Fargate task memory in MiB. Must be a valid value for the given cpu (see https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-cpu-memory-error.html)."
  type        = number

  validation {
    condition = (
      (var.cpu == 256 && contains([512, 1024, 2048], var.memory)) ||
      (var.cpu == 512 && var.memory >= 1024 && var.memory <= 4096 && var.memory % 1024 == 0) ||
      (var.cpu == 1024 && var.memory >= 2048 && var.memory <= 8192 && var.memory % 1024 == 0) ||
      (var.cpu == 2048 && var.memory >= 4096 && var.memory <= 16384 && var.memory % 1024 == 0) ||
      (var.cpu == 4096 && var.memory >= 8192 && var.memory <= 30720 && var.memory % 1024 == 0)
    )
    error_message = "memory must be a valid Fargate value for the given cpu."
  }
}

variable "desired_count" {
  description = "Number of ECS task instances to run."
  type        = number
}

variable "deregistration_delay" {
  description = "Seconds the ALB waits for in-flight connections to drain before deregistering a target."
  type        = number
  default     = 300
}

variable "stop_timeout" {
  description = "Seconds ECS waits after sending SIGTERM before force-killing the container with SIGKILL."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags to apply to ECS resources."
  type        = map(string)
  default     = {}
}

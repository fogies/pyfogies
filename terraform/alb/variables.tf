variable "region" {
  description = "AWS region in which to create ALB resources."
  type        = string
}

variable "name" {
  description = "Name of the ALB."
  type        = string

  validation {
    condition     = length(var.name) <= 32
    error_message = "ALB name must be at most 32 characters."
  }

  validation {
    condition     = can(regex("^[a-zA-Z0-9-]+$", var.name))
    error_message = "ALB name must contain only alphanumeric characters and hyphens."
  }

  validation {
    condition     = !startswith(var.name, "-") && !endswith(var.name, "-")
    error_message = "ALB name must not start or end with a hyphen."
  }

  validation {
    condition     = !startswith(var.name, "internal-")
    error_message = "ALB name must not start with 'internal-'."
  }
}

variable "subnet_ids" {
  description = "Subnet IDs across which to distribute the ALB."
  type        = set(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "An ALB requires subnets in at least two availability zones."
  }
}

variable "security_group_ids" {
  description = "Security group IDs to attach to the ALB."
  type        = set(string)

  validation {
    condition     = length(var.security_group_ids) >= 1
    error_message = "An ALB requires at least one security group."
  }
}

variable "self_signed_certificate" {
  description = "If true, create a self-signed certificate using the ALB's DNS name instead of using certificate_arn."
  type        = bool
  default     = false
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS. Required unless self_signed_certificate is true."
  type        = string
  default     = null

  validation {
    condition     = var.self_signed_certificate || var.certificate_arn != null
    error_message = "certificate_arn is required unless self_signed_certificate is true."
  }
}

variable "tags" {
  description = "Tags to apply to ALB resources."
  type        = map(string)
  default     = {}
}

variable "hosted_zone_name" {
  description = "Route 53 hosted zone name. All hostnames must fall within this zone."
  type        = string
}

variable "hostnames" {
  description = "Hostnames to include in the certificate. The first is the primary; all must be within hosted_zone_name. A Route 53 alias record is created for each."
  type        = list(string)

  validation {
    condition     = length(var.hostnames) >= 1
    error_message = "At least one hostname is required."
  }
}

variable "alb_dns_name" {
  description = "DNS name of the ALB to alias the hostnames to."
  type        = string
}

variable "alb_zone_id" {
  description = "Hosted zone ID of the ALB (for Route 53 alias records)."
  type        = string
}

variable "listener_https_arn" {
  description = "ARN of the ALB HTTPS listener to attach the certificate to."
  type        = string
}

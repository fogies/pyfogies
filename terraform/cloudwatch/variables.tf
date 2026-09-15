variable "name" {
  description = "Name of the CloudWatch log group (e.g. /ecs/my-service)."
  type        = string
}

variable "retention_in_days" {
  description = "Number of days to retain log events. 0 means never expire."
  type        = number
  default     = 0

  validation {
    condition     = contains([0, 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.retention_in_days)
    error_message = "retention_in_days must be 0 (never expire) or one of the values allowed by AWS."
  }
}

variable "tags" {
  description = "Tags to apply to the log group."
  type        = map(string)
  default     = {}
}

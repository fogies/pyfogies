variable "region" {
  description = "AWS region in which to create network resources."
  type        = string
}

variable "availability_zone_count" {
  description = "Number of availability zones in which to create subnets."
  type        = number

  validation {
    condition     = var.availability_zone_count >= 1 && var.availability_zone_count <= 9
    error_message = "availability_zone_count must be between 1 and 9."
  }
}

variable "tags" {
  description = "Tags to apply to network resources."
  type        = map(string)
  default     = {}
}

variable "region" {
  description = "AWS region in which to create network resources."
  type        = string
}

variable "availability_zone_count" {
  description = "Number of availability zones in which to create subnets."
  type        = number
}

variable "tags" {
  description = "Tags to apply to network resources."
  type        = map(string)
  default     = {}
}

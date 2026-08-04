variable "name" {
  description = "Base prefix for backend resources (used to derive bucket name)."
  type        = string
}

variable "region" {
  description = "AWS region in which to create backend resources."
  type        = string
}

variable "states" {
  description = "Logical names of Terraform states to manage within this backend."
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to backend resources."
  type        = map(string)
  default     = {}
}


variable "zone_name" {
  description = "Domain name of the Route 53 hosted zone."
  type        = string
}

variable "mode" {
  description = <<-EOT
    How the hosted zone is provided:
      registered: create zone for a domain registered in this account.
      delegated:  create zone for a domain registered elsewhere.
      existing:   use an existing hosted zone.
  EOT
  type        = string

  validation {
    condition     = contains(["registered", "delegated", "existing"], var.mode)
    error_message = "mode must be one of: registered, delegated, existing."
  }
}

variable "tags" {
  description = "Tags to apply to created resources."
  type        = map(string)
  default     = {}
}

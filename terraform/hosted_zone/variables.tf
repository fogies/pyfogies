variable "zone_name" {
  description = "Domain name of the Route 53 hosted zone."
  type        = string
}

variable "create_zone" {
  description = "If true, create the hosted zone and update the domain registration's name servers. If false, use the existing hosted zone."
  type        = bool
}

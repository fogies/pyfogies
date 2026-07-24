output "zone_id" {
  description = "Route 53 hosted zone ID."
  value       = local.zone_id
}

output "zone_name" {
  description = "Hosted zone domain name."
  value       = var.zone_name
}

output "name_servers" {
  description = "Name servers assigned to the hosted zone."
  value       = local.name_servers
}

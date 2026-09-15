output "hostname" {
  description = "The primary hostname at which the ALB is reachable."
  value       = local.primary_hostname
}

output "hostnames" {
  description = "All hostnames at which the ALB is reachable."
  value       = var.hostnames
}

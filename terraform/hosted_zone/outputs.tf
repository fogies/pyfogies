output "zone_id" {
  description = "Route 53 hosted zone ID."
  value       = aws_route53_zone.zone.zone_id
}

output "zone_name" {
  description = "Hosted zone domain name."
  value       = aws_route53_zone.zone.name
}

output "name_servers" {
  description = "Name servers assigned to the hosted zone."
  value       = aws_route53_zone.zone.name_servers
}

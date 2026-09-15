output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.vpc.id
}

output "subnet_ids" {
  description = "List of subnet IDs, one per availability zone."
  value       = [for az in local.availability_zones : aws_subnet.subnet[az].id]
}

output "availability_zone_to_subnet_id" {
  description = "Map from availability zone to subnet ID."
  value       = { for az in local.availability_zones : az => aws_subnet.subnet[az].id }
}


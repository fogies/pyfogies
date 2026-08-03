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

output "security_group_ids" {
  description = "List of security group IDs attached to the VPC."
  value = [
    aws_vpc.vpc.default_security_group_id,
    aws_security_group.allow_egress_to_anywhere.id,
    aws_security_group.allow_ingress_http_https_from_anywhere.id,
  ]
}

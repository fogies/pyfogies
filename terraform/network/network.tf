locals {
  # Stable netnum by zone letter so adding/removing zones does not renumber existing subnets.
  # Uses the final character of the AZ name (e.g. "a" from "us-west-2a") so this works for any region.
  az_letter_to_netnum = {
    "a" = 0, "b" = 1, "c" = 2, "d" = 3,
    "e" = 4, "f" = 5, "g" = 6, "h" = 7, "i" = 8,
  }
  availability_zones = slice(sort(data.aws_availability_zones.available.names), 0, var.availability_zone_count)
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = var.tags
}

resource "aws_subnet" "subnet" {
  for_each = toset(local.availability_zones)

  availability_zone       = each.value
  cidr_block              = cidrsubnet(aws_vpc.vpc.cidr_block, 8, local.az_letter_to_netnum[substr(each.value, -1, 1)])
  vpc_id                  = aws_vpc.vpc.id
  map_public_ip_on_launch = false

  tags = var.tags
}

resource "aws_internet_gateway" "gateway" {
  vpc_id = aws_vpc.vpc.id

  tags = var.tags
}

resource "aws_route_table" "route_table" {
  vpc_id = aws_vpc.vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gateway.id
  }

  tags = var.tags
}

resource "aws_route_table_association" "route_table" {
  for_each = toset(local.availability_zones)

  subnet_id      = aws_subnet.subnet[each.value].id
  route_table_id = aws_route_table.route_table.id
}

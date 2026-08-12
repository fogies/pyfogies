data "aws_route53_zone" "existing" {
  count = var.create_zone ? 0 : 1
  name  = var.zone_name
}

resource "aws_route53_zone" "zone" {
  count = var.create_zone ? 1 : 0
  name  = var.zone_name
}

resource "aws_route53domains_registered_domain" "domain" {
  count       = var.create_zone ? 1 : 0
  provider    = aws.us_east_1
  domain_name = var.zone_name

  dynamic "name_server" {
    for_each = toset(aws_route53_zone.zone[0].name_servers)
    content {
      name = name_server.value
    }
  }
}

locals {
  zone_id      = var.create_zone ? aws_route53_zone.zone[0].zone_id : data.aws_route53_zone.existing[0].zone_id
  name_servers = var.create_zone ? aws_route53_zone.zone[0].name_servers : data.aws_route53_zone.existing[0].name_servers
}

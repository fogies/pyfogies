data "aws_route53_zone" "existing" {
  count = var.mode == "existing" ? 1 : 0
  name  = var.zone_name
}

resource "aws_route53_zone" "zone" {
  count = local.create_zone ? 1 : 0
  name  = var.zone_name
  tags  = var.tags
}

resource "aws_route53domains_registered_domain" "domain" {
  count       = var.mode == "registered" ? 1 : 0
  provider    = aws.us_east_1
  domain_name = var.zone_name
  tags        = var.tags

  dynamic "name_server" {
    for_each = toset(aws_route53_zone.zone[0].name_servers)
    content {
      name = name_server.value
    }
  }
}

locals {
  create_zone = var.mode != "existing"

  zone_id      = local.create_zone ? aws_route53_zone.zone[0].zone_id : data.aws_route53_zone.existing[0].zone_id
  name_servers = local.create_zone ? aws_route53_zone.zone[0].name_servers : data.aws_route53_zone.existing[0].name_servers
}

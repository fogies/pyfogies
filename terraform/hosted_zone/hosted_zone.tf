resource "aws_route53_zone" "zone" {
  name = var.zone_name
}

resource "aws_route53domains_registered_domain" "domain" {
  provider    = aws.us_east_1
  domain_name = var.zone_name

  dynamic "name_server" {
    for_each = toset(aws_route53_zone.zone.name_servers)
    content {
      name = name_server.value
    }
  }
}

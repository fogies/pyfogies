locals {
  primary_hostname = var.hostnames[0]
  san_hostnames    = slice(var.hostnames, 1, length(var.hostnames))
}

data "aws_route53_zone" "zone" {
  # Disambiguates from a private zone of the same name, since the ALB alias
  # and ACM validation records here must land in the public zone.
  name         = var.hosted_zone_name
  private_zone = false
}

resource "aws_route53_record" "hostname" {
  for_each = toset(var.hostnames)

  zone_id = data.aws_route53_zone.zone.zone_id
  name    = each.value
  type    = "A"

  alias {
    name                   = var.alb_dns_name
    zone_id                = var.alb_zone_id
    evaluate_target_health = true
  }
}

resource "aws_acm_certificate" "cert" {
  domain_name               = local.primary_hostname
  subject_alternative_names = local.san_hostnames
  validation_method         = "DNS"
  tags                      = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

locals {
  dvo_by_hostname = {
    for dvo in aws_acm_certificate.cert.domain_validation_options : dvo.domain_name => dvo
  }
}

resource "aws_route53_record" "cert_validation" {
  # Intentionally keyed by hostnames known at plan time.
  # Terraform can apparently be unstable with for_each on a computed value.
  for_each = toset(var.hostnames)

  zone_id = data.aws_route53_zone.zone.zone_id
  name    = local.dvo_by_hostname[each.value].resource_record_name
  type    = local.dvo_by_hostname[each.value].resource_record_type
  records = [local.dvo_by_hostname[each.value].resource_record_value]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "cert" {
  certificate_arn         = aws_acm_certificate.cert.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

resource "aws_lb_listener_certificate" "cert" {
  listener_arn    = var.listener_https_arn
  certificate_arn = aws_acm_certificate_validation.cert.certificate_arn

  lifecycle {
    # Attach the new certificate before removing the old one so the listener
    # is never left without a valid cert when hostnames change.
    create_before_destroy = true
  }
}

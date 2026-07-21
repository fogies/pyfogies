locals {
  use_self_signed = var.certificate_arn == null
}

# Self-signed certificate path (when no certificate_arn is provided).
# The cert is issued for the ALB's own DNS name, so hostname verification works
# when callers use the certificate_pem output as their trusted CA.

resource "tls_private_key" "key" {
  count     = local.use_self_signed ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_self_signed_cert" "cert" {
  count           = local.use_self_signed ? 1 : 0
  private_key_pem = tls_private_key.key[0].private_key_pem

  subject {
    common_name = aws_lb.alb.dns_name
  }

  dns_names = [aws_lb.alb.dns_name]

  validity_period_hours = 8760

  allowed_uses = [
    "key_encipherment",
    "digital_signature",
    "server_auth",
  ]
}

resource "aws_acm_certificate" "self_signed" {
  count            = local.use_self_signed ? 1 : 0
  private_key      = tls_private_key.key[0].private_key_pem
  certificate_body = tls_self_signed_cert.cert[0].cert_pem
}

locals {
  certificate_arn = local.use_self_signed ? aws_acm_certificate.self_signed[0].arn : var.certificate_arn
  certificate_pem = local.use_self_signed ? tls_self_signed_cert.cert[0].cert_pem : null
}

# Self-signed certificate path (when self_signed_certificate is true).
# The cert is issued for the ALB's own DNS name, so hostname verification works
# when callers use the certificate_pem output as their trusted CA.

resource "tls_private_key" "key" {
  count     = var.self_signed_certificate ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_self_signed_cert" "cert" {
  count           = var.self_signed_certificate ? 1 : 0
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
  count            = var.self_signed_certificate ? 1 : 0
  private_key      = tls_private_key.key[0].private_key_pem
  certificate_body = tls_self_signed_cert.cert[0].cert_pem
}

locals {
  certificate_arn = var.self_signed_certificate ? aws_acm_certificate.self_signed[0].arn : var.certificate_arn
  certificate_pem = var.self_signed_certificate ? tls_self_signed_cert.cert[0].cert_pem : null
}

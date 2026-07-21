output "alb_arn" {
  description = "ARN of the ALB."
  value       = aws_lb.alb.arn
}

output "alb_dns_name" {
  description = "DNS name of the ALB."
  value       = aws_lb.alb.dns_name
}

output "alb_zone_id" {
  description = "Hosted zone ID of the ALB (for Route 53 alias records)."
  value       = aws_lb.alb.zone_id
}

output "listener_http_arn" {
  description = "ARN of the HTTP listener (always redirects to HTTPS)."
  value       = aws_lb_listener.listener_http.arn
}

output "listener_https_arn" {
  description = "ARN of the HTTPS listener."
  value       = aws_lb_listener.listener_https.arn
}

output "certificate_pem" {
  description = "PEM of the certificate. Non-null only when a self-signed certificate was created."
  value       = local.certificate_pem
}

# Security group for a public-facing ALB: allows inbound HTTP/HTTPS from
# anywhere, so the ALB can be reached from the internet.
resource "aws_security_group" "this" {
  name   = var.name
  vpc_id = var.vpc_id

  ingress {
    # Plain HTTP, for the alb_dns module's redirect-to-HTTPS listener.
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    # HTTPS, for the ALB's actual application traffic.
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    # Unrestricted outbound, so the ALB can reach its ECS targets and any
    # other backend regardless of port.
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

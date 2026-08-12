resource "aws_security_group" "allow_egress_to_anywhere" {
  name_prefix = "allow_egress_to_anywhere-"
  vpc_id      = aws_vpc.vpc.id

  egress {
    description = "Allow Egress to Anywhere"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "allow_ingress_http_https_from_anywhere" {
  name_prefix = "allow_ingress_http_https_from_anywhere-"
  vpc_id      = aws_vpc.vpc.id

  ingress {
    description = "Allow Ingress HTTP from Anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow Ingress HTTPS from Anywhere"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

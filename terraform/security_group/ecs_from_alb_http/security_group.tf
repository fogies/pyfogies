# Security group for an ECS task/service: allows inbound traffic on the
# container port only from the ALB's own security group (not the public
# internet directly), so requests must go through the ALB.
resource "aws_security_group" "this" {
  name   = var.name
  vpc_id = var.vpc_id

  ingress {
    # security_groups (not cidr_blocks): only the ALB itself can reach the
    # container port, whatever that port is.
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
  }

  egress {
    # Unrestricted outbound, e.g. so the task can pull its image and reach
    # any AWS APIs or external services it needs.
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

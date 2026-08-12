resource "aws_ecr_repository" "repository" {
  for_each = var.repositories

  name         = each.value
  force_delete = var.force_delete

  tags = var.tags
}

data "aws_ecr_lifecycle_policy_document" "policy_document" {
  for_each = var.repositories

  rule {
    priority    = 1
    description = "Preserve latest."

    action {
      type = "expire"
    }

    selection {
      tag_status       = "tagged"
      tag_pattern_list = ["latest"]
      count_type       = "imageCountMoreThan"
      count_number     = 1
    }
  }

  rule {
    priority    = 2
    description = "Preserve ${var.lifecycle_keep_count} previous images."

    action {
      type = "expire"
    }

    selection {
      tag_status       = "tagged"
      tag_pattern_list = ["*"]
      count_type       = "imageCountMoreThan"
      count_number     = var.lifecycle_keep_count
    }
  }

  rule {
    priority    = 3
    description = "Preserve ${var.lifecycle_keep_days} days of previous images."

    action {
      type = "expire"
    }

    selection {
      tag_status   = "any"
      count_type   = "sinceImagePushed"
      count_unit   = "days"
      count_number = var.lifecycle_keep_days
    }
  }
}

resource "aws_ecr_lifecycle_policy" "policy" {
  for_each = var.repositories

  repository = aws_ecr_repository.repository[each.value].name
  policy     = data.aws_ecr_lifecycle_policy_document.policy_document[each.value].json
}

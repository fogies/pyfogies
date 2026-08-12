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
    description = "Expire tagged images beyond the most recent ${var.lifecycle_keep_count_limit}. Combines with the age rule below: an image needs to satisfy both to survive."

    action {
      type = "expire"
    }

    selection {
      tag_status       = "tagged"
      tag_pattern_list = ["*"]
      count_type       = "imageCountMoreThan"
      count_number     = var.lifecycle_keep_count_limit
    }
  }

  rule {
    priority    = 3
    description = "Expire any image, tagged or not, older than ${var.lifecycle_keep_days_limit} days. Applies even to images within the count limit above."

    action {
      type = "expire"
    }

    selection {
      tag_status   = "any"
      count_type   = "sinceImagePushed"
      count_unit   = "days"
      count_number = var.lifecycle_keep_days_limit
    }
  }
}

resource "aws_ecr_lifecycle_policy" "policy" {
  for_each = var.repositories

  repository = aws_ecr_repository.repository[each.value].name
  policy     = data.aws_ecr_lifecycle_policy_document.policy_document[each.value].json
}

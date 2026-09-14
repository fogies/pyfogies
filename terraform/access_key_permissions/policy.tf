data "aws_iam_user" "user" {
  user_name = var.username
}

data "aws_iam_policy_document" "permissions" {
  dynamic "statement" {
    for_each = var.statements
    content {
      effect    = statement.value.effect
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
}

resource "aws_iam_user_policy" "permissions" {
  name   = "${var.username}-${var.name}"
  user   = data.aws_iam_user.user.user_name
  policy = data.aws_iam_policy_document.permissions.json
}

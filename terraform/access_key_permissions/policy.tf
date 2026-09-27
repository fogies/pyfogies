data "aws_iam_user" "user" {
  user_name = var.username
}

resource "aws_iam_user_policy_attachment" "policies" {
  for_each = toset(var.policies)

  user       = data.aws_iam_user.user.user_name
  policy_arn = each.value
}

# The inline policy is only created when there are statements to grant: an
# inline policy with no statements is not valid.
data "aws_iam_policy_document" "statements" {
  count = length(var.statements) > 0 ? 1 : 0

  dynamic "statement" {
    for_each = var.statements
    content {
      effect    = statement.value.effect
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
}

resource "aws_iam_user_policy" "statements" {
  count = length(var.statements) > 0 ? 1 : 0

  # The name has no meaning to anything that reads it; it only has to be
  # unique per user, so name_prefix leaves the suffix to the provider rather
  # than taking a name from the caller.
  name_prefix = "${var.username}-"
  user        = data.aws_iam_user.user.user_name
  policy      = data.aws_iam_policy_document.statements[0].json
}

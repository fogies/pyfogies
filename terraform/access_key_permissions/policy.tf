data "aws_iam_user" "user" {
  user_name = var.username
}

locals {
  # Statements every user gets, regardless of what the caller passes.
  # S3 buckets must be created in the account regional namespace: a bucket in
  # the global namespace can have its name re-created by another account
  # after it is deleted. An explicit deny overrides any allow, so this holds
  # even for a user granted AdministratorAccess.
  default_statements = [
    {
      effect    = "Deny"
      actions   = ["s3:CreateBucket"]
      resources = ["*"]
      conditions = [
        {
          test     = "StringNotEquals"
          variable = "s3:x-amz-bucket-namespace"
          values   = ["account-regional"]
        },
      ]
    },
  ]

  statements     = concat(local.default_statements, var.statements)
  has_statements = length(local.statements) > 0
}

resource "aws_iam_user_policy_attachment" "policies" {
  for_each = toset(var.policies)

  user       = data.aws_iam_user.user.user_name
  policy_arn = each.value
}

# The policy is only created when there are statements to grant: a policy
# with no statements is not valid. The default statements mean there are
# always some, but the guard stays in case the defaults become optional.
data "aws_iam_policy_document" "statements" {
  count = local.has_statements ? 1 : 0

  dynamic "statement" {
    for_each = local.statements
    content {
      effect    = statement.value.effect
      actions   = statement.value.actions
      resources = statement.value.resources

      dynamic "condition" {
        for_each = statement.value.conditions
        content {
          test     = condition.value.test
          variable = condition.value.variable
          values   = condition.value.values
        }
      }
    }
  }
}

# A managed policy, not an inline one: the size limit of a managed policy is
# 6,144 characters, where all of a user's inline policies together are limited
# to 2,048. The caller never has to know about either limit.
resource "aws_iam_policy" "statements" {
  count = local.has_statements ? 1 : 0

  # The name has no meaning to anything that reads it; it only has to be
  # unique in the account, so name_prefix leaves the suffix to the provider
  # rather than taking a name from the caller.
  name_prefix = "${var.username}-"
  policy      = data.aws_iam_policy_document.statements[0].json
}

resource "aws_iam_user_policy_attachment" "statements" {
  count = local.has_statements ? 1 : 0

  user       = data.aws_iam_user.user.user_name
  policy_arn = aws_iam_policy.statements[0].arn
}

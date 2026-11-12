resource "aws_iam_user" "claude_sync" {
  name = var.name

  # Destroying the user also deletes its access keys.
  force_destroy = true
}

# Only the operations claude-sync performs: list, read, write, and delete objects.
module "claude_sync_permissions" {
  source = "../access_key_permissions"

  username = var.name

  statements = [
    {
      effect    = "Allow"
      actions   = ["s3:ListBucket"]
      resources = [aws_s3_bucket.claude_sync.arn]
    },
    {
      effect    = "Allow"
      actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      resources = ["${aws_s3_bucket.claude_sync.arn}/*"]
    },
    # The record of deleted sessions is read and written, and never deleted.
    # Listing is only so that a record that doesn't exist yet is reported as
    # missing, rather than as access denied.
    {
      effect    = "Allow"
      actions   = ["s3:ListBucket"]
      resources = [aws_s3_bucket.deletions.arn]
    },
    {
      effect    = "Allow"
      actions   = ["s3:GetObject", "s3:PutObject"]
      resources = ["${aws_s3_bucket.deletions.arn}/*"]
    },
  ]

  # The permissions module looks the user up by name, so wait until it exists.
  depends_on = [aws_iam_user.claude_sync]
}

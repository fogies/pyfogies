# A second bucket, for the record of deleted sessions (see fogies.tools.claude_sync_deletions).
#
# It is separate from the bucket claude-sync syncs to, because claude-sync owns
# the root of that bucket: it lists every object in it, and its reset and
# `init --force` delete every object in it. A bucket of its own cannot be
# touched by claude-sync, whatever version of it is used.

locals {
  deletions_bucket_name = "${var.name}-deletions-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.region}-an"
}

resource "aws_s3_bucket" "deletions" {
  bucket           = local.deletions_bucket_name
  bucket_namespace = "account-regional"

  # Destroying claude-sync leaves nothing that uses the record,
  # so destroying the bucket also deletes its contents.
  force_destroy = true

  lifecycle {
    precondition {
      condition     = length(local.deletions_bucket_name) <= 63
      error_message = "The deletions bucket name, including the account and region suffix, must be at most 63 characters."
    }
  }
}

# Versioning allows recovery from a bad write, which would otherwise overwrite the record.
resource "aws_s3_bucket_versioning" "deletions" {
  bucket = aws_s3_bucket.deletions.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Bound the cost of versioning by expiring old versions.
resource "aws_s3_bucket_lifecycle_configuration" "deletions" {
  bucket = aws_s3_bucket.deletions.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.deletions]
}

resource "aws_s3_bucket_public_access_block" "deletions" {
  bucket = aws_s3_bucket.deletions.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "deletions" {
  bucket = aws_s3_bucket.deletions.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

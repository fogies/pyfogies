data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  # A bucket in the account regional namespace can only be created by this
  # account, and can never be re-created by another account. The namespace
  # requires the account ID and region suffix, which count towards the
  # 63 character limit.
  bucket_name = "${var.name}-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.region}-an"
}

resource "aws_s3_bucket" "claude_sync" {
  bucket           = local.bucket_name
  bucket_namespace = "account-regional"

  # The bucket only holds copies of what each machine already has,
  # so destroying it also deletes its contents.
  force_destroy = true

  lifecycle {
    precondition {
      condition     = length(local.bucket_name) <= 63
      error_message = "The bucket name, including the account and region suffix, must be at most 63 characters."
    }
  }
}

# Versioning allows recovery from a bad sync, which would otherwise overwrite or delete.
resource "aws_s3_bucket_versioning" "claude_sync" {
  bucket = aws_s3_bucket.claude_sync.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Bound the cost of versioning by expiring old versions.
resource "aws_s3_bucket_lifecycle_configuration" "claude_sync" {
  bucket = aws_s3_bucket.claude_sync.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    # Remove delete markers once the versions they covered have expired.
    expiration {
      expired_object_delete_marker = true
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.claude_sync]
}

resource "aws_s3_bucket_public_access_block" "claude_sync" {
  bucket = aws_s3_bucket.claude_sync.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Sessions can contain sensitive output, so ensure all bucket content is encrypted.
# claude-sync also encrypts each file before upload.
resource "aws_s3_bucket_server_side_encryption_configuration" "claude_sync" {
  bucket = aws_s3_bucket.claude_sync.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  region = data.aws_region.current.region

  # We include the region in the bucket name
  # because of the large delays associated with deleting and creating a bucket in a different region.
  # The account regional namespace also requires the region in the name.
  #
  # A bucket in the account regional namespace can only be created by this
  # account, and can never be re-created by another account. The namespace
  # requires the account ID and region suffix, which count towards the
  # 63 character limit.
  bucket_name = "${var.backend_name}-${data.aws_caller_identity.current.account_id}-${local.region}-an"
}

# Use a single bucket. 
# Different states will be stored using keys.
resource "aws_s3_bucket" "state" {
  bucket           = local.bucket_name
  bucket_namespace = "account-regional"

  # Explicitly and intentionally false. 
  # Resources with every state must be explicitly destroyed before the bucket can be deleted.
  # This ensures no resources are orphaned by deleting the state that captures their creation.
  # Use backend_delete_state_objects to clear state files after confirming all resources are destroyed.
  force_destroy = false

  tags = var.tags

  lifecycle {
    precondition {
      condition     = length(local.bucket_name) <= 63
      error_message = "The bucket name, including the account and region suffix, must be at most 63 characters."
    }
  }
}

# Ensure versioning within the bucket.
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Ensure the bucket cannot accidentally be made public.
resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Ensure all bucket content is encrypted.
# Terraform state will often include secrets.
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

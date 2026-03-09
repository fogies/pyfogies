# Use a single bucket. 
# Different states will be stored using keys.
resource "aws_s3_bucket" "state" {
  bucket        = "${var.name}-bucket"
  force_destroy = var.force_destroy

  tags = merge(
    {
      Name = "${var.name}-bucket"
    },
    var.tags,
  )
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

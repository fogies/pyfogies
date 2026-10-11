output "bucket" {
  description = "Name of the S3 bucket claude-sync stores to."
  value       = aws_s3_bucket.claude_sync.bucket
}

output "region" {
  description = "Region of the S3 bucket."
  value       = aws_s3_bucket.claude_sync.region
}

output "user_name" {
  description = "Name of the IAM user claude-sync signs in as. Its access key is created outside of terraform, so that the secret is not stored in state."
  value       = aws_iam_user.claude_sync.name
}

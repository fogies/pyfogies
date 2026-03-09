output "bucket_name" {
  description = "Name of the S3 bucket used for Terraform state."
  value       = aws_s3_bucket.state.id
}

output "lock_name" {
  description = "Name of the DynamoDB table used for state locking."
  value       = aws_dynamodb_table.lock.name
}

output "state_keys" {
  description = "Map of logical state name to key prefix in the state bucket."
  value = {
    for state in var.states :
    state => "${state}/terraform.tfstate"
  }
}

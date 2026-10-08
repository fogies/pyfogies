output "backend_name" {
  description = "Name given to the backend, from which the bucket name is derived."
  value       = var.backend_name
}

output "bucket_name" {
  description = "Name of the S3 bucket used for Terraform state."
  value       = aws_s3_bucket.state.id
}

output "region" {
  description = "AWS region in which the backend resources were created."
  value       = local.region
}

output "state_keys" {
  description = "Map of state name to key prefix in the state bucket."
  value = {
    for state_name in var.state_names :
    state_name => "${state_name}/terraform.tfstate"
  }
}

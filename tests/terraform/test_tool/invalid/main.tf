terraform {
  required_version = "~> 1.14.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.6.0"
    }
  }
}

variable "test_content" {
  description = "Content written by the Terraform tool test."
  type        = string
}

variable "test_path" {
  description = "Path to the temporary resource created by the test."
  type        = string
}

resource "local_file" "test_file" {
  # Write a small marker file so the test
  # can verify Terraform applied successfully.
  filename = var.test_path
  content  = var.test_content
}

output "file_path" {
  description = "Path of the test file."
  value       = local_file.test_file.filename
}

output "file_content" {
  description = "Content of the test file."
  value       = local_file.test_file.content
}

output "invalid" {
  description = "Intentional invalid reference for testing apply failure."
  value       = local_file.invalid_test_file.filename
}

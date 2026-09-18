terraform {
  required_version = "~> 1.15"

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
  # Write a small marker file so the test can verify this independent
  # resource still applies even though always_fails fails separately.
  filename = var.test_path
  content  = var.test_content
}

resource "null_resource" "always_fails" {
  # Intentionally fails at apply time (not plan/validation time), with no
  # dependency on local_file.test_file, so the test can verify a partial
  # apply failure still leaves the independent resource created.
  provisioner "local-exec" {
    command = "exit 1"
  }
}

output "file_path" {
  description = "Path of the test file."
  value       = local_file.test_file.filename
}

output "file_content" {
  description = "Content of the test file."
  value       = local_file.test_file.content
}

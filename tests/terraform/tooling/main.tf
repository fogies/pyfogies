terraform {
  required_version = "~> 1.14.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.6.0"
    }
  }
}

variable "filename" {
  description = "Path of the test file."
  type        = string
}

variable "content" {
  description = "Content to write to the test file."
  type        = string
  default     = "created by terraform"
}

resource "local_file" "test_file" {
  filename = var.filename
  content  = var.content
}

output "filename" {
  description = "Path of the test file."
  value       = local_file.test_file.filename
}

output "content" {
  description = "Content of the test file."
  value       = local_file.test_file.content
}

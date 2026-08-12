terraform {
  required_version = "~> 1.14.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.6.0"
    }
  }
}

variable "content" {
  type = string
}

resource "local_file" "test_file" {
  filename = "${path.module}/test_resource.txt"
  content  = var.content
}

output "file_path" {
  description = "Path of the test file."
  value       = local_file.test_file.filename
}

output "file_content" {
  description = "Content of the test file."
  value       = local_file.test_file.content
}

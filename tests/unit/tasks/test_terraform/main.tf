terraform {
  required_version = "~> 1.14.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.6.0"
    }
  }
}

# No variables: get_task_apply/get_task_destroy do not support passing
# tfvars, so this fixture must be self-contained.
resource "local_file" "test_file" {
  filename = "${path.module}/test_resource.txt"
  content  = "test_task_apply_and_destroy"
}

output "file_path" {
  description = "Path of the test file."
  value       = local_file.test_file.filename
}

output "file_content" {
  description = "Content of the test file."
  value       = local_file.test_file.content
}

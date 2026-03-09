terraform {
  required_version = "~> 1.14.0"

  backend "s3" {
    bucket         = "pyfogies-test-backend-bucket"
    key            = "test-state-a/terraform.tfstate"
    dynamodb_table = "pyfogies-test-backend-lock"
    region         = "us-east-1"
  }

  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

variable "test_value" {
  description = "Value stored by the module. Used to trigger state changes."
  type        = string
}

resource "null_resource" "test_state" {
  triggers = {
    value = var.test_value
  }
}

output "test_value" {
  description = "The value passed into the module."
  value       = var.test_value
}

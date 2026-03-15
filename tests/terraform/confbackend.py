"""Tests for the Terraform backend module."""

# Name of backend to be shared across all Terraform testing.
PYFOGIES_TEST_TERRAFORM_BACKEND_NAME: str = "pyfogies-test-backend"
PYFOGIES_TEST_TERRAFORM_BACKEND_REGION: str = "us-west-2"
PYFOGIES_TEST_TERRAFORM_BACKEND_STATES: list[str] = [
    "test-backend",
]

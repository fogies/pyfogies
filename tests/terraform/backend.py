"""Tests for the Terraform backend module."""

from enum import Enum

# Name of backend to be shared across all Terraform testing.
PYFOGIES_TEST_TERRAFORM_BACKEND_NAME: str = "pyfogies-test-backend"
PYFOGIES_TEST_TERRAFORM_BACKEND_REGION: str = "us-west-2"


class PYFOGIES_TEST_TERRAFORM_BACKEND_STATES(str, Enum):
    TEST_BACKEND = "test-backend"

"""Tests for the Terraform backend module."""

from enum import Enum

# Name of backend to be shared across all Terraform testing.
PYFOGIES_TEST_TERRAFORM_BACKEND_NAME: str = "pyfogies-test-backend"
PYFOGIES_TEST_TERRAFORM_BACKEND_REGION: str = "us-west-2"


class PYFOGIES_TEST_TERRAFORM_BACKEND_STATES(str, Enum):
    PYFOGIES_TEST_CERTIFICATE = "pyfogies-test-certificate"
    TEST_ALB = "test-alb"
    TEST_BACKEND = "test-backend"
    TEST_CERTIFICATE = "test-certificate"
    TEST_ECR = "test-ecr"
    TEST_NETWORK = "test-network"

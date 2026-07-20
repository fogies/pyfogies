"""Shared constants for backend in Terraform tests."""

from enum import Enum

PYFOGIES_TEST_TERRAFORM_BACKEND_NAME: str = "pyfogies-test-backend"


class PYFOGIES_TEST_TERRAFORM_BACKEND_STATES(str, Enum):
    PYFOGIES_TEST_CERTIFICATE = "pyfogies-test-certificate"
    TEST_ALB = "test-alb"
    TEST_BACKEND = "test-backend"
    TEST_CERTIFICATE = "test-certificate"
    TEST_ECR = "test-ecr"
    TEST_NETWORK = "test-network"

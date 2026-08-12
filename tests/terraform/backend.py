"""Shared constants for backend in Terraform tests."""

from enum import Enum

PYFOGIES_TEST_TERRAFORM_BACKEND_NAME: str = "pyfogies-test-backend"


class PyfogiesTestTerraformBackendStates(str, Enum):
    TEST_ALB_DNS = "test-alb-dns"
    TEST_ALB_SELF_SIGNED = "test-alb-self-signed"
    TEST_BACKEND = "test-backend"
    TEST_ECR = "test-ecr"
    TEST_NETWORK = "test-network"

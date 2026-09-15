"""Shared pytest configuration for all tests."""

from tests.pyfogies_tests_config import pyfogies_test_config as _pyfogies_test_config
from tests.terraform.pyfogies_test_aws_environ import (
    pyfogies_test_aws_environ as _pyfogies_test_aws_environ,
)

# Exported for pytest discovery.
pyfogies_test_aws_environ = _pyfogies_test_aws_environ
pyfogies_test_config = _pyfogies_test_config

"""Shared pytest configuration for tests under tests/terraform."""

from tests.pyfogies_tests_config import pyfogies_test_config as _pyfogies_test_config
from tests.terraform.pyfogies_test_aws_environ import (
    pyfogies_test_aws_environ as _pyfogies_test_aws_environ,
)
from tests.terraform.pyfogies_test_backend import (
    pyfogies_test_backend as _pyfogies_test_backend,
)

# Exported for pytest discovery.
pyfogies_test_aws_environ = _pyfogies_test_aws_environ
pyfogies_test_backend = _pyfogies_test_backend
pyfogies_test_config = _pyfogies_test_config

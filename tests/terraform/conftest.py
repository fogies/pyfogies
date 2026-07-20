"""Shared pytest configuration for tests under tests/terraform."""

from tests.terraform.pyfogies_test_aws_environ import (
    pyfogies_test_aws_environ as _pyfogies_test_aws_environ,
)
from tests.terraform.pyfogies_test_backend import (
    pyfogies_test_backend as _pyfogies_test_backend,
)
from tests.terraform.pyfogies_test_certificate import (
    pyfogies_test_certificate as _pyfogies_test_certificate,
)

# Exported for pytest discovery.
pyfogies_test_aws_environ = _pyfogies_test_aws_environ
pyfogies_test_backend = _pyfogies_test_backend
pyfogies_test_certificate = _pyfogies_test_certificate

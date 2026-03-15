"""Shared pytest configuration for tests under tests/terraform."""

from tests.terraform.pyfogies_test_backend import pyfogies_test_backend as _pyfogies_test_backend

# Exported for pytest discovery.
pyfogies_test_backend = _pyfogies_test_backend

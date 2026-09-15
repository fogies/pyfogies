"""Shared pytest configuration for tests under tests/terraform."""

from tests.terraform.pyfogies_test_alb_self_signed import (
    pyfogies_test_alb_self_signed as _pyfogies_test_alb_self_signed,
)
from tests.terraform.pyfogies_test_backend import (
    pyfogies_test_backend as _pyfogies_test_backend,
)
from tests.terraform.pyfogies_test_network import (
    pyfogies_test_network as _pyfogies_test_network,
)

# Exported for pytest discovery.
pyfogies_test_alb_self_signed = _pyfogies_test_alb_self_signed
pyfogies_test_backend = _pyfogies_test_backend
pyfogies_test_network = _pyfogies_test_network

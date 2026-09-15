"""Session-scoped network fixture shared across test modules."""

import pathlib
from collections.abc import Iterator

import pytest
from pydantic import BaseModel

from fogies.terraform.backend import BackendOutput
from fogies.terraform.network import NetworkOutput
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfbackend,
    terraform_tfvars,
)
from tasks.paths import PATH_STAGING_BINARY_CACHE, PATH_TEST_BACKEND_STATUS
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PyfogiesTestTerraformBackendStates

_TEST_NETWORK_MODULE = pathlib.Path(__file__).parent / "test_network"


class _TestNetworkVars(BaseModel):
    region: str


class _TestNetworkOutput(BaseModel):
    network: NetworkOutput


@pytest.fixture(scope="session")
def pyfogies_test_network(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_backend: BackendOutput,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[NetworkOutput]:
    """Session-scoped VPC, subnets, and security groups. Shared by all test modules that need a network."""
    command_params = CommandParams(in_stream=False)
    tmp_path = tmp_path_factory.mktemp("pyfogies-test-network")
    tfbackend_path = tmp_path / "pyfogies-test-network.tfbackend"
    tfvars_path = tmp_path / "pyfogies-test-network.tfvars.json"
    backend = pyfogies_test_backend[
        PyfogiesTestTerraformBackendStates.TEST_NETWORK.value
    ]

    with (
        terraform_tfbackend(
            path=tfbackend_path,
            backend=backend,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestNetworkVars(region=pyfogies_test_config.aws.region),
        ) as tfvars_path,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=_TEST_NETWORK_MODULE,
            tfvars_path=tfvars_path,
            tfbackend_path=tfbackend_path,
            backend=backend,
            backend_status_path=PATH_TEST_BACKEND_STATUS,
            init_on_entry=True,
            init_params=InitParams(upgrade=True, reconfigure=True),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestNetworkOutput,
        ) as tf_output,
    ):
        yield tf_output.network

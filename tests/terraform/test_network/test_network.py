"""Test Terraform network module."""

import pathlib

from fogies_paths import PATH_STAGING_BINARY_CACHE
from pydantic import BaseModel

from fogies.terraform.backend import BackendOutput
from fogies.terraform.network import NetworkOutput
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfbackend_s3,
    terraform_tfvars,
)
from tests.terraform.backend import (
    PYFOGIES_TEST_TERRAFORM_BACKEND_REGION,
    PYFOGIES_TEST_TERRAFORM_BACKEND_STATES,
)

_TEST_REGION = PYFOGIES_TEST_TERRAFORM_BACKEND_REGION


class _TestRegionVars(BaseModel):
    region: str


class _TestNetworkOutput(BaseModel):
    network: NetworkOutput


def test_network_output(
    pyfogies_test_backend: BackendOutput,
    tmp_path: pathlib.Path,
) -> None:
    """Network module creates VPC, subnets, and security groups with expected output."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent
    tfbackend_path = tmp_path / "test-network.s3.tfbackend"
    tfvars_path = tmp_path / "test-network.tfvars.json"

    with (
        terraform_tfbackend_s3(
            path=tfbackend_path,
            backend=pyfogies_test_backend,
            state=PYFOGIES_TEST_TERRAFORM_BACKEND_STATES.TEST_NETWORK.value,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestRegionVars(region=_TEST_REGION),
        ) as tfvars_path,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=module_path,
            tfvars_path=tfvars_path,
            tfbackend_path=tfbackend_path,
            init_on_entry=True,
            init_params=InitParams(upgrade=True, reconfigure=True),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            delete_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestNetworkOutput,
        ) as output,
    ):
        assert isinstance(output.network, NetworkOutput)

        assert output.network.vpc_id.startswith("vpc-")

        assert len(output.network.subnet_ids) == 2
        assert all(sid.startswith("subnet-") for sid in output.network.subnet_ids)

        assert len(output.network.availability_zone_to_subnet_id) == 2
        assert set(output.network.availability_zone_to_subnet_id.values()) == set(
            output.network.subnet_ids
        )

        assert len(output.network.security_group_ids) == 3
        assert all(sgid.startswith("sg-") for sgid in output.network.security_group_ids)

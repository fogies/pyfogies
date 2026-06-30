"""Test Terraform ECR module."""

import pathlib

from fogies_paths import PATH_STAGING_BINARY_CACHE
from pydantic import BaseModel

from fogies.terraform.backend import BackendOutput
from fogies.terraform.ecr import EcrOutput
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


class _TestEcrOutput(BaseModel):
    ecr: EcrOutput


def test_ecr_output(
    pyfogies_test_backend: BackendOutput,
    tmp_path: pathlib.Path,
) -> None:
    """ECR module creates a repository and output matches expected structure."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent
    tfbackend_path = tmp_path / "test-ecr.s3.tfbackend"
    tfvars_path = tmp_path / "test-ecr.tfvars.json"

    with (
        terraform_tfbackend_s3(
            path=tfbackend_path,
            backend=pyfogies_test_backend,
            state=PYFOGIES_TEST_TERRAFORM_BACKEND_STATES.TEST_ECR.value,
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
            output_model=_TestEcrOutput,
        ) as output,
    ):
        assert isinstance(output.ecr, EcrOutput)

        expected_registry_suffix = ".dkr.ecr.{}.amazonaws.com".format(_TEST_REGION)
        assert output.ecr.registry_url.endswith(expected_registry_suffix)

        assert set(output.ecr.repositories.keys()) == {
            "pyfogies-test-ecr-a",
            "pyfogies-test-ecr-b",
        }
        for name, repo in output.ecr.repositories.items():
            assert repo.name == name
            assert repo.arn.startswith("arn:aws:ecr:")
            assert repo.repository_url.startswith(output.ecr.registry_url)

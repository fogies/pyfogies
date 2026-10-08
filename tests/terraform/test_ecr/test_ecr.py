"""Test Terraform ECR module."""

import pathlib

from pydantic import BaseModel

from fogies.terraform.backend import BackendOutput
from fogies.terraform.ecr import EcrOutput
from fogies.tools.aws_environ import AwsEnviron
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfbackend,
    terraform_tfvars,
)
from tasks.paths import STAGING_BINARY_CACHE_PATH, TEST_BACKEND_STATUS_PATH
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PyfogiesTestBackendStates

_TEST_ECR_TAGS = {"Project": "pyfogies-test-ecr"}


class _TestEcrVars(BaseModel):
    region: str
    tags: dict[str, str] = {}


class _TestEcrOutput(BaseModel):
    ecr: EcrOutput


def test_ecr_output(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_aws_environ: AwsEnviron,
    pyfogies_test_backend: BackendOutput,
    tmp_path: pathlib.Path,
) -> None:
    """ECR module creates a repository and output matches expected structure."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent
    tfbackend_path = tmp_path / "test-ecr.tfbackend"
    tfvars_path = tmp_path / "test-ecr.tfvars.json"

    backend = pyfogies_test_backend[PyfogiesTestBackendStates.TEST_ECR]

    with (
        terraform_tfbackend(
            path=tfbackend_path,
            backend=backend,
            aws_environ=pyfogies_test_aws_environ,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestEcrVars(
                region=pyfogies_test_config.aws.region, tags=_TEST_ECR_TAGS
            ),
        ) as tfvars_path,
        terraform_output(
            binary_cache_path=STAGING_BINARY_CACHE_PATH,
            command_params=command_params,
            module_path=module_path,
            tfvars_path=tfvars_path,
            tfbackend_path=tfbackend_path,
            backend=backend,
            aws_environ=pyfogies_test_aws_environ,
            backend_status_path=TEST_BACKEND_STATUS_PATH,
            init_on_entry=True,
            init_params=InitParams(upgrade=True, reconfigure=True),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestEcrOutput,
        ) as output,
    ):
        assert isinstance(output.ecr, EcrOutput)

        expected_registry_suffix = ".dkr.ecr.{}.amazonaws.com".format(
            pyfogies_test_config.aws.region
        )
        assert output.ecr.registry_url.endswith(expected_registry_suffix)

        assert set(output.ecr.repositories.keys()) == {
            "pyfogies-test-ecr-a",
            "pyfogies-test-ecr-b",
        }
        for name, repo in output.ecr.repositories.items():
            assert repo.name == name
            assert repo.arn.startswith("arn:aws:ecr:")
            assert repo.repository_url.startswith(output.ecr.registry_url)

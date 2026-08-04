"""Fixtures for the pyfogies-test-backend Terraform module."""

import pathlib
from collections.abc import Iterator

import pytest
from pydantic import BaseModel

from fogies.terraform.backend import (
    BackendOutput,
    BackendVars,
    backend_delete_state_objects,
)
from fogies.tools.aws_environ import AwsEnviron
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfvars,
)
from tasks.paths import PATH_STAGING_BINARY_CACHE
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import (
    PYFOGIES_TEST_TERRAFORM_BACKEND_NAME,
    PYFOGIES_TEST_TERRAFORM_BACKEND_STATES,
)


class _PyFogiesTestBackendOutput(BaseModel):
    backend: BackendOutput


@pytest.fixture(scope="session")
def pyfogies_test_backend(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_aws_environ: AwsEnviron,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[BackendOutput]:
    """Apply the backend module; yield output; destroy on teardown."""
    _ = pyfogies_test_aws_environ
    command_params = CommandParams(in_stream=False)
    backend_module_path = pathlib.Path(__file__).resolve().parent
    tmp_path = tmp_path_factory.mktemp("pyfogies-test-backend")
    tfvars_path = tmp_path / "pyfogies-test-backend.tfvars.json"

    with (
        terraform_tfvars(
            path=tfvars_path,
            variables=BackendVars(
                name=PYFOGIES_TEST_TERRAFORM_BACKEND_NAME,
                region=pyfogies_test_config.aws.region,
                states=[s.value for s in PYFOGIES_TEST_TERRAFORM_BACKEND_STATES],
            ),
        ) as tfvars_path,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=backend_module_path,
            tfvars_path=tfvars_path,
            init_on_entry=True,
            init_params=InitParams(
                upgrade=True,
                reconfigure=True,
            ),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_PyFogiesTestBackendOutput,
        ) as output,
    ):
        try:
            yield output.backend
        finally:
            # Verifies no resources remain, then clears bucket contents so
            # Terraform can destroy it.
            backend_delete_state_objects(output=output.backend)

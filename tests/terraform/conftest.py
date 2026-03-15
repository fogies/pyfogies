"""Shared pytest configuration and fixtures for tests under tests/terraform."""

import pathlib
from collections.abc import Iterator

import pytest
from pydantic import BaseModel

from paths import (
    AWS_PROFILE_PYFOGIES_TEST,
    PATH_SECRETS_AWS,
    PATH_STAGING_BINARY_CACHE,
)
from fogies.terraform.backend import BackendOutput, BackendVars
from fogies.tools.aws_environ import aws_environ
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfvars,
)


# Name of backend to be shared in testing.


class _PyFogiesTestBackendVars(BaseModel):
    backend: BackendVars


class _PyFogiesTestBackendOutput(BaseModel):
    backend: BackendOutput


@pytest.fixture(scope="session")
def pyfogies_test_backend(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[BackendOutput]:
    """Apply the backend module; yield output; destroy on teardown."""
    command_params = CommandParams(in_stream=False)
    backend_module_path = (
        pathlib.Path(__file__).resolve().parent / "pyfogies-test-backend"
    )
    tmp_path = tmp_path_factory.mktemp("pyfogies-test-backend")
    tfvars_path = tmp_path / "pyfogies-test-backend.tfvars.json"

    with (
        aws_environ(
            profiles_path=PATH_SECRETS_AWS,
            profile=AWS_PROFILE_PYFOGIES_TEST,
        ),
        terraform_tfvars(
            path=tfvars_path,
            variables=_PyFogiesTestBackendVars(
                backend=BackendVars(
                    name=TEST_TERRAFORM_BACKEND_NAME,
                    states=TEST_TERRAFORM_BACKEND_STATES,
                    tags={},
                    # force_destroy is intentionally false to require explicit cleanup of resources.
                    # Every test module should destroy its own resources.
                    # This fixture confirms that before destroying their states.
                ),
            ),
        ) as tfvars_path,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=backend_module_path,
            tfvars_path=tfvars_path,
            init_on_entry=True,
            init_params=InitParams(upgrade=True, reconfigure=True,),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            delete_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_PyFogiesTestBackendOutput,
        ) as output,
    ):
        yield output.backend

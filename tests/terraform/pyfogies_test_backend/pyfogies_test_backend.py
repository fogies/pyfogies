"""Fixtures for the pyfogies-test-backend Terraform module."""

import pathlib
from collections.abc import Iterator

import pytest
from pydantic import BaseModel

from fogies.terraform.backend import BackendOutput, BackendStatus, BackendVars
from fogies.tools.aws_environ import AwsEnviron
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_tfvars,
)
from fogies.tools.terraform_backend import terraform_backend
from tasks.paths import STAGING_BINARY_CACHE_PATH, TEST_BACKEND_STATUS_PATH
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PyfogiesTestBackendStates

_TEST_BACKEND_SESSION_NAME = "pyfogies-test-backend-session"
_TEST_BACKEND_SESSION_TAGS = {"Project": "pyfogies-test-backend-session"}


class _PyFogiesTestBackendOutput(BaseModel):
    backend: BackendOutput


@pytest.fixture(scope="session")
def pyfogies_test_backend(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_aws_environ: AwsEnviron,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[BackendOutput]:
    """Apply the backend module; yield output; destroy on teardown.

    Removes the status file at the end if nothing is left applied.
    """
    _ = pyfogies_test_aws_environ
    command_params = CommandParams(in_stream=False)
    backend_module_path = pathlib.Path(__file__).resolve().parent
    tmp_path = tmp_path_factory.mktemp("pyfogies-test-backend")
    tfvars_path = tmp_path / "pyfogies-test-backend.tfvars.json"

    with (
        terraform_tfvars(
            path=tfvars_path,
            variables=BackendVars(
                name=_TEST_BACKEND_SESSION_NAME,
                region=pyfogies_test_config.aws.region,
                states=list(PyfogiesTestBackendStates),
                tags=_TEST_BACKEND_SESSION_TAGS,
            ),
        ) as tfvars_path,
        terraform_backend(
            binary_cache_path=STAGING_BINARY_CACHE_PATH,
            command_params=command_params,
            module_path=backend_module_path,
            backend_status_path=TEST_BACKEND_STATUS_PATH,
            tfvars_path=tfvars_path,
            init_on_entry=True,
            init_params=InitParams(upgrade=True, reconfigure=True),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_PyFogiesTestBackendOutput,
            output_model_get_backend=lambda o: o.backend,
        ) as output,
    ):
        yield output.backend

    # Everything is destroyed, so the status file has nothing to report.
    # It stays if anything is still applied, e.g. after a failed destroy.
    status = BackendStatus.load(path=TEST_BACKEND_STATUS_PATH)
    if not status.backend.applied and not any(
        state.applied for state in status.states.values()
    ):
        TEST_BACKEND_STATUS_PATH.unlink(missing_ok=True)

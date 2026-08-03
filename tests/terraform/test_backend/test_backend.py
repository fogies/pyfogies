"""Test Terraform backend module."""

import pathlib
from collections.abc import Iterator

import pytest
from pydantic import BaseModel

from fogies.terraform.backend import BackendOutput, BackendVars
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfbackend,
    terraform_tfvars,
)
from tasks.paths import (
    PATH_STAGING_BINARY_CACHE,
)
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PYFOGIES_TEST_TERRAFORM_BACKEND_STATES


class _TestBackendOutput(BaseModel):
    backend: BackendOutput


class _TestStateVars(BaseModel):
    test_value: str


class _TestStateOutput(BaseModel):
    test_value: str


_TEST_BACKEND_NESTED_BACKEND_NAME = "test-backend-nested-backend"
_TEST_BACKEND_NESTED_BACKEND_STATES = ["test-state-a", "test-state-b"]


@pytest.fixture(scope="module")
def nested_backend_output(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_backend: BackendOutput,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[BackendOutput]:
    """Apply the backend module; yield output; destroy on teardown."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent / "backend"
    tmp_path = tmp_path_factory.mktemp("test-backend")
    tfbackend_path = tmp_path / "test-backend.tfbackend"
    tfvars_path = tmp_path / "test-backend.tfvars.json"

    with (
        terraform_tfbackend(
            path=tfbackend_path,
            backend=pyfogies_test_backend[
                PYFOGIES_TEST_TERRAFORM_BACKEND_STATES.TEST_BACKEND.value
            ],
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=BackendVars(
                name=_TEST_BACKEND_NESTED_BACKEND_NAME,
                region=pyfogies_test_config.aws.region,
                states=_TEST_BACKEND_NESTED_BACKEND_STATES,
                tags={},
                # force_destroy can be used here
                # because there are no AWS resources created in tests.
                # There is nothing that could be orphaned by a deletion.
                force_destroy=True,
            ),
        ) as tfvars_path,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=module_path,
            tfvars_path=tfvars_path,
            tfbackend_path=tfbackend_path,
            init_on_entry=True,
            init_params=InitParams(
                upgrade=True,
                reconfigure=True,
            ),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestBackendOutput,
        ) as output,
    ):
        yield output.backend


def test_backend_output(nested_backend_output: BackendOutput) -> None:
    """Backend module output matches expected bucket and state keys."""
    expected_bucket_name = "{}-bucket-{}".format(
        _TEST_BACKEND_NESTED_BACKEND_NAME,
        nested_backend_output.region,
    )
    expected_state_keys = {
        s: "{}/terraform.tfstate".format(s) for s in _TEST_BACKEND_NESTED_BACKEND_STATES
    }

    assert isinstance(nested_backend_output, BackendOutput)
    assert nested_backend_output.bucket_name == expected_bucket_name
    assert nested_backend_output.state_keys == expected_state_keys


def test_state_a_and_state_b(
    nested_backend_output: BackendOutput,
    tmp_path: pathlib.Path,
) -> None:
    """Apply state_a and state_b, using backend bucket."""
    # Ensure backend fixture.
    assert nested_backend_output is not None

    command_params = CommandParams(in_stream=False)
    backend_path = pathlib.Path(__file__).parent
    state_a_module_path = backend_path / "state_a"
    state_b_module_path = backend_path / "state_b"

    tfbackend_a_path = tmp_path / "state_a.tfbackend"
    tfbackend_b_path = tmp_path / "state_b.tfbackend"
    tfvars_a = tmp_path / "state_a.tfvars.json"
    tfvars_b = tmp_path / "state_b.tfvars.json"
    expected_value_a = "test-state-a"
    expected_value_b = "test-state-b"

    with (
        terraform_tfbackend(
            path=tfbackend_a_path,
            backend=nested_backend_output["test-state-a"],
        ) as tfbackend_a_path,
        terraform_tfbackend(
            path=tfbackend_b_path,
            backend=nested_backend_output["test-state-b"],
        ) as tfbackend_b_path,
        terraform_tfvars(
            path=tfvars_a,
            variables=_TestStateVars(test_value=expected_value_a),
        ) as tfvars_a,
        terraform_tfvars(
            path=tfvars_b,
            variables=_TestStateVars(test_value=expected_value_b),
        ) as tfvars_b,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=state_a_module_path,
            tfvars_path=tfvars_a,
            tfbackend_path=tfbackend_a_path,
            init_on_entry=True,
            init_params=InitParams(
                upgrade=True,
                reconfigure=True,
            ),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestStateOutput,
        ) as output_a,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=state_b_module_path,
            tfvars_path=tfvars_b,
            tfbackend_path=tfbackend_b_path,
            init_on_entry=True,
            init_params=InitParams(
                upgrade=True,
                reconfigure=True,
            ),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestStateOutput,
        ) as output_b,
    ):
        assert isinstance(output_a, _TestStateOutput)
        assert output_a.test_value == expected_value_a
        assert isinstance(output_b, _TestStateOutput)
        assert output_b.test_value == expected_value_b


def test_invalid_state_c(
    nested_backend_output: BackendOutput,
    tmp_path: pathlib.Path,
) -> None:
    """Applying invalid_state_c fails due to disallowed key prefix."""
    # Ensure backend fixture.
    assert nested_backend_output is not None

    tfbackend_c_path = tmp_path / "invalid_state_c.tfbackend"

    with pytest.raises(ValueError):
        with (
            terraform_tfbackend(
                path=tfbackend_c_path,
                backend=nested_backend_output["invalid_state_c"],
            ) as tfbackend_c_path,
        ):
            # Apply should fail.
            pass

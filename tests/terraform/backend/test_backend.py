"""Test Terraform backend module."""

import pathlib
from collections.abc import Iterator

import pytest
from invoke.exceptions import UnexpectedExit
from paths import (
    PATH_SECRETS_AWS,
    PATH_STAGING_BINARY_CACHE,
    SECRETS_AWS_PROFILE_PYFOGIES_TEST,
)
from pydantic import BaseModel

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


class _TestBackendVars(BaseModel):
    backend: BackendVars


class _TestBackendOutput(BaseModel):
    backend: BackendOutput


class _TestStateVars(BaseModel):
    test_value: str


class _TestStateOutput(BaseModel):
    test_value: str


_BACKEND_NAME = "pyfogies-test-backend"
_BACKEND_STATES = ["test-state-a", "test-state-b"]


@pytest.fixture(scope="module")
def backend_output(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[_TestBackendOutput]:
    """Apply the backend module; yield output; destroy on teardown."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent / "backend"
    tmp_path = tmp_path_factory.mktemp("backend")
    tfvars_path = tmp_path / "backend.tfvars.json"

    with (
        aws_environ(
            profiles_path=PATH_SECRETS_AWS, profile=SECRETS_AWS_PROFILE_PYFOGIES_TEST
        ),
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestBackendVars(
                backend=BackendVars(
                    name=_BACKEND_NAME,
                    states=_BACKEND_STATES,
                    tags={},
                    force_destroy=True,
                ),
            ),
        ) as tfvars_path,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=module_path,
            tfvars_path=tfvars_path,
            init_on_entry=True,
            init_params=InitParams(upgrade=True),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            delete_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestBackendOutput,
        ) as output,
    ):
        yield output


def test_backend_output(backend_output: _TestBackendOutput) -> None:
    """Backend module output matches expected bucket, lock, and state keys."""
    expected_bucket_name = "{}-bucket".format(_BACKEND_NAME)
    expected_lock_name = "{}-lock".format(_BACKEND_NAME)
    expected_state_keys = {s: "{}/terraform.tfstate".format(s) for s in _BACKEND_STATES}

    assert isinstance(backend_output, _TestBackendOutput)
    assert backend_output.backend.bucket_name == expected_bucket_name
    assert backend_output.backend.lock_name == expected_lock_name
    assert backend_output.backend.state_keys == expected_state_keys


def test_state_a_and_state_b(
    backend_output: _TestBackendOutput,
    tmp_path: pathlib.Path,
) -> None:
    """Apply state_a and state_b, using backend bucket."""
    # Ensure backend fixture.
    assert backend_output is not None

    command_params = CommandParams(in_stream=False)
    backend_path = pathlib.Path(__file__).parent
    state_a_module_path = backend_path / "state_a"
    state_b_module_path = backend_path / "state_b"

    tfvars_a = tmp_path / "state_a.tfvars.json"
    tfvars_b = tmp_path / "state_b.tfvars.json"
    expected_value_a = "test-state-a"
    expected_value_b = "test-state-b"

    with (
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
            init_on_entry=True,
            init_params=InitParams(upgrade=True),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            delete_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestStateOutput,
        ) as output_a,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=state_b_module_path,
            tfvars_path=tfvars_b,
            init_on_entry=True,
            init_params=InitParams(upgrade=True),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            delete_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestStateOutput,
        ) as output_b,
    ):
        assert isinstance(output_a, _TestStateOutput)
        assert output_a.test_value == expected_value_a
        assert isinstance(output_b, _TestStateOutput)
        assert output_b.test_value == expected_value_b


@pytest.mark.xfail(
    strict=True,
    reason="Have not implemented enforcement of key prefix. Found S3 bucket policies did not support without additional IAM configuration.",
)
def test_invalid_state_c(
    backend_output: _TestBackendOutput,
    tmp_path: pathlib.Path,
) -> None:
    """Applying invalid_state_c fails due to disallowed key prefix."""
    # Ensure backend fixture.
    assert backend_output is not None

    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent / "invalid_state_c"

    tfvars_c = tmp_path / "invalid_state_c.tfvars.json"

    with pytest.raises(UnexpectedExit):
        with (
            terraform_tfvars(
                path=tfvars_c,
                variables=_TestStateVars(test_value="test-invalid-state-c"),
            ) as tfvars_c,
            terraform_output(
                binary_cache_path=PATH_STAGING_BINARY_CACHE,
                command_params=command_params,
                module_path=module_path,
                tfvars_path=tfvars_c,
                init_on_entry=True,
                init_params=InitParams(upgrade=True),
                apply_on_entry=True,
                apply_params=ApplyParams(auto_approve=True),
                delete_on_exit=True,
                destroy_params=DestroyParams(auto_approve=True),
                output_model=_TestStateOutput,
            ) as _,
        ):
            # Apply should fail.
            pass

"""Test the Terraform tool."""

import pathlib
import subprocess

import pytest
from pydantic import BaseModel

from fogies.tools.command import CommandParams
from fogies.tools.terraform import InitParams, terraform
from tasks.paths import STAGING_BINARY_CACHE_PATH


def test_terraform_is_available() -> None:
    """Context manager provides a working executable."""
    with terraform(binary_cache_path=STAGING_BINARY_CACHE_PATH) as tf:
        # Verify the executable exists.
        assert tf.binary_path.exists()

        # Run the executable and verify the version matches.
        result = subprocess.run(
            [str(tf.binary_path), "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert tf.binary_version in result.stdout


class _RequiredOutputs(BaseModel):
    backend: str


class _OptionalOutputs(BaseModel):
    backend: str | None = None


@pytest.mark.parametrize(
    ("output_model", "expected"),
    [
        (_RequiredOutputs, None),
        (_OptionalOutputs, _OptionalOutputs()),
    ],
)
def test_terraform_output_when_nothing_applied(
    tmp_path: pathlib.Path,
    output_model: type[BaseModel],
    expected: BaseModel | None,
) -> None:
    """A never-applied module has no outputs.

    output() returns None if the model needs outputs, and the model itself
    if it accepts none.
    """
    module_path = tmp_path / "module"
    module_path.mkdir()
    _ = (module_path / "main.tf").write_text("")
    command_params = CommandParams(in_stream=False, cwd=module_path)

    with terraform(
        binary_cache_path=STAGING_BINARY_CACHE_PATH,
        command_params=command_params,
        module_path=module_path,
        init_on_entry=True,
        init_params=InitParams(),
    ) as tf:
        assert (
            tf.output(
                command_params=command_params,
                module_path=module_path,
                output_model=output_model,
            )
            == expected
        )

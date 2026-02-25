"""Test Terraform tool."""

import json
import pathlib
import subprocess

from pydantic import BaseModel

from paths import PATH_STAGING_BINARY_CACHE

from fogies.tools.command import SubprocessCommandParams
from fogies.tools.terraform import terraform, terraform_tfvars


def test_terraform_is_available() -> None:
    """Context manager provides a working executable."""
    with terraform(path_binary_cache=PATH_STAGING_BINARY_CACHE) as tf:
        # Verify the executable exists.
        assert tf.path.exists()

        # Run the executable and verify the version matches.
        result = subprocess.run(
            [str(tf.path), "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert tf.version in result.stdout


def test_terraform_tfvars(tmp_path: pathlib.Path) -> None:
    """terraform_tfvars writes the file and yields the path."""
    class Vars(BaseModel):
        key: str

    with terraform_tfvars(
        path=tmp_path / "cm_vars.tfvars.json",
        variables=Vars(key="value"),
    ) as var_path:
        assert var_path.exists()
        data = json.loads(var_path.read_text())
        assert data == {"key": "value"}


def test_init_apply_destroy() -> None:
    """Apply and then destroy the tooling module using the Terraform tool."""
    command_params = SubprocessCommandParams(capture_output=False)
    module_path = pathlib.Path(__file__).resolve().parent / "tool"

    with terraform(path_binary_cache=PATH_STAGING_BINARY_CACHE) as tf:
        init_result = tf.init(
            command_params=command_params,
            module_path=module_path,
        )
        assert init_result.returncode == 0, init_result.stderr

        apply_result = tf.apply(
            command_params=command_params,
            module_path=module_path,
            tfvars_path=module_path / "terraform.tfvars",
            auto_approve=True,
        )
        try:
            assert apply_result.returncode == 0
        finally:
            destroy_result = tf.destroy(
                command_params=command_params,
                module_path=module_path,
                tfvars_path=module_path / "terraform.tfvars",
                auto_approve=True,
            )
            assert destroy_result.returncode == 0

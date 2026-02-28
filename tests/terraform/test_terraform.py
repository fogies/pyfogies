"""Test Terraform tool."""

import pathlib
import subprocess

from paths import PATH_STAGING_BINARY_CACHE
from pydantic import BaseModel

from fogies.tools.command import CommandParams
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
        path=tmp_path / "vars.tfvars.json",
        variables=Vars(key="value"),
    ) as var_path:
        assert var_path.exists()
        vars_loaded = Vars.model_validate_json(var_path.read_text())
        assert vars_loaded == Vars(key="value")


def test_init_apply_output_destroy(tmp_path: pathlib.Path) -> None:
    """Apply and then destroy the tooling module using the Terraform tool."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent / "tool"

    class ToolVars(BaseModel):
        test_path: str
        test_content: str

    class ToolOutput(BaseModel):
        file_path: str
        file_content: str

    expected_tfvars_path = tmp_path / "tool.tfvars.json"
    expected_file_path = tmp_path / "test_resource.txt"
    expected_file_content = "test_init_apply_output_destroy"
    expected_output = ToolOutput(
        file_path=str(expected_file_path),
        file_content=expected_file_content,
    )

    with terraform(path_binary_cache=PATH_STAGING_BINARY_CACHE) as tf:
        init_result = tf.init(
            command_params=command_params,
            module_path=module_path,
        )
        assert init_result.exited == 0, init_result.stderr

        with terraform_tfvars(
            path=expected_tfvars_path,
            variables=ToolVars(
                test_path=str(expected_file_path),
                test_content=expected_file_content,
            ),
        ) as tfvars_path:
            apply_result = tf.apply(
                command_params=command_params,
                module_path=module_path,
                tfvars_path=tfvars_path,
                auto_approve=True,
            )
            try:
                assert apply_result.exited == 0
                assert expected_file_path.exists()
                assert expected_file_path.read_text().strip() == expected_file_content

                # Imagine Terraform exposes a typed output helper that returns
                # Pydantic models from `terraform output -json`.
                tool_output = tf.output(
                    command_params=command_params,
                    module_path=module_path,
                    output_model=ToolOutput,
                )
                assert isinstance(tool_output, ToolOutput)
                assert tool_output == expected_output
            finally:
                destroy_result = tf.destroy(
                    command_params=command_params,
                    module_path=module_path,
                    tfvars_path=tfvars_path,
                    auto_approve=True,
                )
                assert destroy_result.exited == 0

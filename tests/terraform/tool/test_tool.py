"""Test applying the tooling Terraform config via the Terraform tool."""

import pathlib

from fogies.tools.command import SubprocessCommandParams
from fogies.tools.terraform import terraform
from paths import PATH_STAGING_BINARY_CACHE


def test_tool():
    """Apply and then destroy the tooling module using the Terraform tool."""
    command_params = SubprocessCommandParams(capture_output=False)
    path_module = pathlib.Path(__file__).parent

    with terraform(path_binary_cache=PATH_STAGING_BINARY_CACHE) as tf:
        init_result = tf.init(
            command_params=command_params,
            path_module=path_module,
        )
        assert init_result.returncode == 0, init_result.stderr

        apply_result = tf.apply(
            command_params=command_params,
            path_module=path_module,
            auto_approve=True,
        )
        try:
            assert apply_result.returncode == 0
            assert apply_result.stdout is not None
        finally:
            destroy_result = tf.destroy(
                command_params=command_params,
                path_module=path_module,
                auto_approve=True,
            )
            assert destroy_result.returncode == 0

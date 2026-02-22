"""Test applying the tooling Terraform config via the Terraform tool."""

import pathlib

from fogies.tools.terraform import SubprocessRunParams, terraform
from paths import PATH_STAGING_BINARY_CACHE


def test_tooling():
    """Apply and then destroy the tooling module using the Terraform tool."""
    path_module = pathlib.Path(__file__).parent
    run_params = SubprocessRunParams(capture_output=False)

    with terraform(path_binary_cache=PATH_STAGING_BINARY_CACHE) as tf:
        init_result = tf.init(
            run_params=run_params,
            path_module=path_module,
        )
        assert init_result.returncode == 0, init_result.stderr

        apply_result = tf.apply(
            run_params=run_params,
            path_module=path_module,
            auto_approve=True,
        )
        try:
            assert apply_result.returncode == 0
            assert apply_result.stdout is not None
        finally:
            destroy_result = tf.destroy(
                run_params=run_params,
                path_module=path_module,
                auto_approve=True,
            )
            assert destroy_result.returncode == 0

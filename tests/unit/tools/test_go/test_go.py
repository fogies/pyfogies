"""Test Go tool."""

import pathlib

from fogies.tools.command import CommandParams, command_run
from fogies.tools.go import go
from tasks.paths import PATH_STAGING_BINARY_CACHE


def test_go_install_builds_and_runs_local_module(tmp_path: pathlib.Path) -> None:
    """install() builds a local module; the built binary runs and does real work."""
    module_path = pathlib.Path(__file__).parent / "valid"
    gobin_path = tmp_path / "gobin"
    command_params = CommandParams(in_stream=False, cwd=module_path)

    with go(binary_cache_path=PATH_STAGING_BINARY_CACHE) as go_tool:
        install_result = go_tool.install(
            command_params=command_params,
            module=".",
            gobin_path=gobin_path,
            raise_if_env_exists=False,
        )
        assert install_result.exited == 0, install_result.stderr

        built_exe_path = gobin_path / "fogies-test-go-valid.exe"
        assert built_exe_path.exists()

        marker_path = tmp_path / "marker.txt"
        run_result = command_run(
            command=built_exe_path,
            command_params=command_params,
            args=[str(marker_path)],
        )
        assert run_result.exited == 0
        assert marker_path.read_text() == "fogies-test-go-valid"

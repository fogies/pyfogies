"""Test Terraform tool."""

import pathlib

import pytest
from invoke.exceptions import UnexpectedExit
from pydantic import BaseModel

from fogies.terraform.backend import BackendConfig
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform,
    terraform_output,
    terraform_tfbackend,
    terraform_tfvars,
)
from tasks.paths import PATH_STAGING_BINARY_CACHE


class _ToolVars(BaseModel):
    test_path: str
    test_content: str


class _ToolOutput(BaseModel):
    file_path: str
    file_content: str


def test_terraform_tfvars(tmp_path: pathlib.Path) -> None:
    """terraform_tfvars writes the file and yields the path; delete_on_exit removes the file."""

    class Vars(BaseModel):
        key: str

    path = tmp_path / "vars.tfvars.json"
    with terraform_tfvars(
        path=path,
        variables=Vars(key="value"),
    ) as var_path:
        assert var_path.exists()
        assert Vars.model_validate_json(var_path.read_text()) == Vars(key="value")

    assert not path.exists()


def test_terraform_tfbackend(tmp_path: pathlib.Path) -> None:
    """terraform_tfbackend writes the file and yields the path; delete_on_exit removes the file."""
    backend = BackendConfig(
        state="test-state",
        bucket_name="my-bucket",
        region="us-west-2",
        key="test-state/terraform.tfstate",
    )
    path = tmp_path / "backend.tfbackend"
    with terraform_tfbackend(path=path, backend=backend) as backend_path:
        text = backend_path.read_text(encoding="utf-8")
        assert 'region = "us-west-2"' in text
        assert 'bucket = "my-bucket"' in text
        assert 'key = "test-state/terraform.tfstate"' in text
        assert "use_lockfile = true" in text
    assert not path.exists()


def test_terraform_init_apply_output_destroy(tmp_path: pathlib.Path) -> None:
    """Apply and then destroy the tooling module using the Terraform tool."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent / "valid"

    expected_tfvars_path = tmp_path / "tool.tfvars.json"
    expected_file_path = tmp_path / "test_resource.txt"
    expected_file_content = "test_terraform_init_apply_output_destroy"
    expected_output = _ToolOutput(
        file_path=str(expected_file_path),
        file_content=expected_file_content,
    )

    with (
        terraform_tfvars(
            path=expected_tfvars_path,
            variables=_ToolVars(
                test_path=str(expected_file_path),
                test_content=expected_file_content,
            ),
        ) as tfvars_path,
        terraform(binary_cache_path=PATH_STAGING_BINARY_CACHE) as tf,
    ):
        init_result = tf.init(
            command_params=command_params,
            module_path=module_path,
            init_params=InitParams(upgrade=True),
        )
        assert init_result.exited == 0, init_result.stderr

        apply_result = tf.apply(
            command_params=command_params,
            module_path=module_path,
            tfvars_path=tfvars_path,
            apply_params=ApplyParams(auto_approve=True),
        )
        try:
            assert apply_result.exited == 0
            assert expected_file_path.exists()
            assert expected_file_path.read_text().strip() == expected_file_content

            tool_output = tf.output(
                command_params=command_params,
                module_path=module_path,
                output_model=_ToolOutput,
            )
            assert isinstance(tool_output, _ToolOutput)
            assert tool_output == expected_output
        finally:
            destroy_result = tf.destroy(
                command_params=command_params,
                module_path=module_path,
                tfvars_path=tfvars_path,
                destroy_params=DestroyParams(auto_approve=True),
            )
            assert destroy_result.exited == 0


def test_terraform_apply_resolves_relative_tfvars_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """apply/init/destroy resolve a relative tfvars_path/tfbackend_path themselves.

    terraform runs with cwd=module_path, which differs from wherever the cwd
    was when tfvars_path was written; a relative path must still resolve
    against that original cwd, not against module_path.
    """
    binary_cache_path = PATH_STAGING_BINARY_CACHE.resolve()
    module_path = pathlib.Path(__file__).parent / "valid"

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)

    command_params = CommandParams(in_stream=False)
    expected_file_path = tmp_path / "test_resource.txt"
    expected_file_content = "test_terraform_apply_resolves_relative_tfvars_path"
    relative_tfvars_path = pathlib.Path("tool.tfvars.json")

    with (
        terraform_tfvars(
            path=relative_tfvars_path,
            variables=_ToolVars(
                test_path=str(expected_file_path),
                test_content=expected_file_content,
            ),
        ) as tfvars_path,
        terraform(binary_cache_path=binary_cache_path) as tf,
    ):
        assert not tfvars_path.is_absolute()

        _ = tf.init(
            command_params=command_params,
            module_path=module_path,
            init_params=InitParams(upgrade=True),
        )
        apply_result = tf.apply(
            command_params=command_params,
            module_path=module_path,
            tfvars_path=tfvars_path,
            apply_params=ApplyParams(auto_approve=True),
        )
        try:
            assert apply_result.exited == 0
            assert expected_file_path.exists()
            assert expected_file_path.read_text().strip() == expected_file_content
        finally:
            destroy_result = tf.destroy(
                command_params=command_params,
                module_path=module_path,
                tfvars_path=tfvars_path,
                destroy_params=DestroyParams(auto_approve=True),
            )
            assert destroy_result.exited == 0


def test_terraform_entry_exit(tmp_path: pathlib.Path) -> None:
    """Context manager runs init/apply on entry and destroy on exit; test only calls output."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent / "valid"

    tfvars_path = tmp_path / "tool.tfvars.json"
    expected_file_path = tmp_path / "test_resource.txt"
    expected_file_content = "test_terraform_entry_exit"
    expected_output = _ToolOutput(
        file_path=str(expected_file_path),
        file_content=expected_file_content,
    )

    with (
        terraform_tfvars(
            path=tfvars_path,
            variables=_ToolVars(
                test_path=str(expected_file_path),
                test_content=expected_file_content,
            ),
        ) as tfvars_path,
        terraform(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=module_path,
            tfvars_path=tfvars_path,
            init_on_entry=True,
            init_params=InitParams(upgrade=True),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
        ) as tf,
    ):
        assert expected_file_path.exists()
        assert expected_file_path.read_text().strip() == expected_file_content

        tool_output = tf.output(
            command_params=command_params,
            module_path=module_path,
            output_model=_ToolOutput,
        )
        assert isinstance(tool_output, _ToolOutput)
        assert tool_output == expected_output


def test_terraform_output(tmp_path: pathlib.Path) -> None:
    """terraform_output runs init/apply/output/destroy and returns the output."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent / "valid"

    tfvars_path = tmp_path / "tool.tfvars.json"
    expected_file_path = tmp_path / "test_resource_output.txt"
    expected_file_content = "test_terraform_output"
    expected_output = _ToolOutput(
        file_path=str(expected_file_path),
        file_content=expected_file_content,
    )

    with (
        terraform_tfvars(
            path=tfvars_path,
            variables=_ToolVars(
                test_path=str(expected_file_path),
                test_content=expected_file_content,
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
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_ToolOutput,
        ) as tool_output,
    ):
        assert expected_file_path.exists()
        assert expected_file_path.read_text().strip() == expected_file_content

        assert isinstance(tool_output, _ToolOutput)
        assert tool_output == expected_output


def test_terraform_apply_partial_failure_still_destroys(tmp_path: pathlib.Path) -> None:
    """destroy_on_exit still runs and cleans up when apply_on_entry partially fails."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent / "partial_failure"

    tfvars_path = tmp_path / "tool.tfvars.json"
    expected_file_path = tmp_path / "test_resource_partial_failure.txt"

    with terraform_tfvars(
        path=tfvars_path,
        variables=_ToolVars(
            test_path=str(expected_file_path),
            test_content="test_terraform_apply_partial_failure_still_destroys",
        ),
    ) as tfvars_path:
        # First, confirm the module itself really does leave the independent
        # local_file resource behind when the unrelated null_resource fails --
        # otherwise the assertions below would pass vacuously even without the
        # fix, since there would be nothing to clean up in the first place.
        with terraform(binary_cache_path=PATH_STAGING_BINARY_CACHE) as tf:
            _ = tf.init(
                command_params=command_params,
                module_path=module_path,
                init_params=InitParams(upgrade=True),
            )
            with pytest.raises(UnexpectedExit):
                _ = tf.apply(
                    command_params=command_params,
                    module_path=module_path,
                    tfvars_path=tfvars_path,
                    apply_params=ApplyParams(auto_approve=True),
                )
            assert expected_file_path.exists(), (
                "expected the independent resource to be created despite "
                "the unrelated resource's apply failure"
            )

            _ = tf.destroy(
                command_params=command_params,
                module_path=module_path,
                tfvars_path=tfvars_path,
                destroy_params=DestroyParams(auto_approve=True),
            )
            assert not expected_file_path.exists()

        # Now confirm terraform()'s own apply_on_entry/destroy_on_exit wiring
        # reaches the same end state automatically -- destroy_on_exit must
        # still run despite apply_on_entry raising. This is the behavior
        # terraform()'s apply/finally ordering was fixed for.
        with pytest.raises(UnexpectedExit):
            with terraform(
                binary_cache_path=PATH_STAGING_BINARY_CACHE,
                command_params=command_params,
                module_path=module_path,
                tfvars_path=tfvars_path,
                init_on_entry=True,
                init_params=InitParams(upgrade=True),
                apply_on_entry=True,
                apply_params=ApplyParams(auto_approve=True),
                destroy_on_exit=True,
                destroy_params=DestroyParams(auto_approve=True),
            ):
                pass

        assert not expected_file_path.exists()


def test_terraform_output_invalid_module_raises(tmp_path: pathlib.Path) -> None:
    """terraform_output with invalid module raises when apply fails."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent / "invalid"

    tfvars_path = tmp_path / "tool.tfvars.json"
    expected_file_path = tmp_path / "test_resource_invalid.txt"
    expected_file_content = "test_terraform_output_invalid"

    with terraform_tfvars(
        path=tfvars_path,
        variables=_ToolVars(
            test_path=str(expected_file_path),
            test_content=expected_file_content,
        ),
    ) as tfvars_path:
        with pytest.raises(UnexpectedExit):
            with terraform_output(
                binary_cache_path=PATH_STAGING_BINARY_CACHE,
                command_params=command_params,
                module_path=module_path,
                tfvars_path=tfvars_path,
                init_on_entry=True,
                init_params=InitParams(upgrade=True),
                apply_on_entry=True,
                apply_params=ApplyParams(auto_approve=True),
                destroy_on_exit=True,
                destroy_params=DestroyParams(auto_approve=True),
                output_model=_ToolOutput,
            ) as _:
                pass

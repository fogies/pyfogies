"""Tool combining the generic Terraform CLI wrapper with backend state tracking."""

import pathlib
from collections.abc import Generator
from contextlib import contextmanager

from fogies.terraform.backend import (
    BackendOutput,
    BackendStatus,
    backend_delete_state_objects,
)
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform,
    terraform_output,
)


@contextmanager
def terraform_backend_apply(
    *,
    binary_cache_path: pathlib.Path,
    command_params: CommandParams,
    module_path: pathlib.Path,
    backend_status_path: pathlib.Path,
    tfvars_path: pathlib.Path | list[pathlib.Path] | None = None,
    init_on_entry: bool = True,
    init_params: InitParams | None = None,
    apply_params: ApplyParams | None = None,
) -> Generator[BackendOutput]:
    """Apply the backend module itself, and record it as applied."""
    with terraform_output(
        binary_cache_path=binary_cache_path,
        command_params=command_params,
        module_path=module_path,
        tfvars_path=tfvars_path,
        init_on_entry=init_on_entry,
        init_params=init_params,
        apply_on_entry=True,
        apply_params=apply_params,
        destroy_on_exit=False,
        output_model=BackendOutput,
    ) as output:
        backend_status = BackendStatus.load(path=backend_status_path)
        backend_status.backend.applied = True
        backend_status.save(path=backend_status_path)
        yield output


def terraform_backend_destroy(
    *,
    binary_cache_path: pathlib.Path,
    command_params: CommandParams,
    module_path: pathlib.Path,
    backend_status_path: pathlib.Path,
    init_on_entry: bool = True,
    init_params: InitParams | None = None,
    destroy_params: DestroyParams | None = None,
) -> None:
    """Safely destroy the backend module, and record it as destroyed.

    Reads the backend module's own real output, then deletes its state
    objects (which verifies every declared state is empty of resources
    first) before destroying it. Raises if any declared state still has
    resources, regardless of how this is invoked.
    """
    with terraform(
        binary_cache_path=binary_cache_path,
        command_params=command_params,
        module_path=module_path,
        init_on_entry=init_on_entry,
        init_params=init_params,
    ) as tf:
        output = tf.output(
            command_params=command_params,
            module_path=module_path,
            output_model=BackendOutput,
        )

        backend_delete_state_objects(output=output)

        _ = tf.destroy(
            command_params=command_params,
            module_path=module_path,
            destroy_params=destroy_params,
        )

    backend_status = BackendStatus.load(path=backend_status_path)
    backend_status.backend.applied = False
    backend_status.save(path=backend_status_path)

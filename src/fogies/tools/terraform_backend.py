"""Tool combining the generic Terraform CLI wrapper with backend state tracking."""

import pathlib
from collections.abc import Callable, Generator
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
    TerraformOutputModel,
    terraform,
)


@contextmanager
def terraform_backend(
    *,
    version: str | None = None,
    binary_cache_path: pathlib.Path,
    command_params: CommandParams,
    module_path: pathlib.Path,
    backend_status_path: pathlib.Path,
    tfbackend_path: pathlib.Path | None = None,
    tfvars_path: pathlib.Path | list[pathlib.Path] | None = None,
    init_on_entry: bool = False,
    init_params: InitParams | None = None,
    apply_on_entry: bool = False,
    apply_params: ApplyParams | None = None,
    destroy_on_exit: bool = False,
    destroy_params: DestroyParams | None = None,
    output_model: type[TerraformOutputModel],
    output_model_get_backend: Callable[[TerraformOutputModel], BackendOutput],
) -> Generator[TerraformOutputModel]:
    """Apply and/or destroy a Terraform backend module, with state tracking.

    Mirrors terraform_output(), adding backend status tracking and safe
    state-object deletion before destroy. backend_status_path is updated
    after apply (applied=True) and after destroy (applied=False).
    output_model_get_backend extracts BackendOutput from the output model.
    """
    with terraform(
        version=version,
        binary_cache_path=binary_cache_path,
        command_params=command_params,
        module_path=module_path,
        tfbackend_path=tfbackend_path,
        tfvars_path=tfvars_path,
        init_on_entry=init_on_entry,
        init_params=init_params,
        apply_on_entry=apply_on_entry,
        apply_params=apply_params,
        destroy_on_exit=False,  # Intentionally false, destroy handled in finally block.
    ) as tf:
        output = tf.output(
            command_params=command_params,
            module_path=module_path,
            output_model=output_model,
        )

        if apply_on_entry:
            backend_status = BackendStatus.load(path=backend_status_path)
            backend_status.backend.applied = True
            backend_status.save(path=backend_status_path)

        try:
            yield output
        finally:
            # Destroy handled in three steps.
            if destroy_on_exit:
                backend_delete_state_objects(output=output_model_get_backend(output))

                _ = tf.destroy(
                    command_params=command_params,
                    module_path=module_path,
                    tfvars_path=tfvars_path,
                    destroy_params=destroy_params,
                )

                backend_status = BackendStatus.load(path=backend_status_path)
                backend_status.backend.applied = False
                backend_status.save(path=backend_status_path)

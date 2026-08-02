"""Tasks for applying and destroying a Terraform backend configuration."""

import pathlib
from contextlib import ExitStack
from typing import Callable, cast

from invoke.context import Context
from invoke.tasks import Task, task

from fogies.tools.aws_environ import aws_environ
from fogies.tools.command import CommandParams
from fogies.tools.terraform import ApplyParams, DestroyParams, InitParams
from fogies.tools.terraform_backend import (
    terraform_backend_apply,
    terraform_backend_destroy,
)


def get_task_backend_apply(
    *,
    module_path: pathlib.Path,
    binary_cache_path: pathlib.Path,
    backend_status_path: pathlib.Path,
    aws_profiles_path: pathlib.Path | None = None,
    aws_profile: str | None = None,
    default_init: bool = True,
    default_init_upgrade: bool = False,
    default_init_reconfigure: bool = False,
    default_apply_auto_approve: bool = False,
    default_output: bool = False,
) -> Task[Callable[[Context, bool, bool, bool, bool, bool], None]]:
    @task(name="apply")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_apply(
        context: Context,
        init: bool = default_init,
        init_upgrade: bool = default_init_upgrade,
        init_reconfigure: bool = default_init_reconfigure,
        apply_auto_approve: bool = default_apply_auto_approve,
        output: bool = default_output,
    ) -> None:
        """
        Apply a Terraform backend configuration, and record it as applied.

        Flags:
          --init                Run terraform init before apply (downloads providers, sets up backend).
          --init-upgrade        Pass -upgrade to init; checks for newer provider versions within constraints.
          --init-reconfigure    Pass -reconfigure to init; re-initializes backend from scratch.
          --apply-auto-approve  Skip Terraform's interactive confirmation prompt.
          --output              Print terraform output as JSON after apply.

        --init-upgrade and --init-reconfigure require --init.
        """
        if init_upgrade and not init:
            raise ValueError("--init-upgrade requires --init")
        if init_reconfigure and not init:
            raise ValueError("--init-reconfigure requires --init")

        command_params = CommandParams(context=context)
        init_params = (
            InitParams(upgrade=init_upgrade, reconfigure=init_reconfigure)
            if init
            else None
        )

        with ExitStack() as stack:
            if aws_profiles_path is not None and aws_profile is not None:
                _ = stack.enter_context(
                    aws_environ(profiles_path=aws_profiles_path, profile=aws_profile)
                )

            output_result = stack.enter_context(
                terraform_backend_apply(
                    binary_cache_path=binary_cache_path,
                    command_params=command_params,
                    module_path=module_path,
                    backend_status_path=backend_status_path,
                    init_on_entry=init,
                    init_params=init_params,
                    apply_params=ApplyParams(auto_approve=apply_auto_approve),
                )
            )

            if output:
                print(output_result.model_dump_json(indent=2))

    return cast(
        Task[Callable[[Context, bool, bool, bool, bool, bool], None]], task_apply
    )


def get_task_backend_destroy(
    *,
    module_path: pathlib.Path,
    binary_cache_path: pathlib.Path,
    backend_status_path: pathlib.Path,
    aws_profiles_path: pathlib.Path | None = None,
    aws_profile: str | None = None,
    default_init: bool = True,
    default_init_upgrade: bool = False,
    default_init_reconfigure: bool = False,
    default_destroy_auto_approve: bool = False,
) -> Task[Callable[[Context, bool, bool, bool, bool], None]]:
    @task(name="destroy")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_destroy(
        context: Context,
        init: bool = default_init,
        init_upgrade: bool = default_init_upgrade,
        init_reconfigure: bool = default_init_reconfigure,
        destroy_auto_approve: bool = default_destroy_auto_approve,
    ) -> None:
        """
        Destroy a Terraform backend configuration, and record it as destroyed.

        Reads the backend module's own output, verifies every state it
        declares is empty of resources, then clears the bucket's state
        objects before destroying it. Refuses (raises) if any declared state
        still has resources, regardless of how this task is invoked.

        Flags:
          --init                 Run terraform init before destroy (downloads providers, sets up backend).
          --init-upgrade         Pass -upgrade to init; checks for newer provider versions within constraints.
          --init-reconfigure     Pass -reconfigure to init; re-initializes backend from scratch.
          --destroy-auto-approve Skip Terraform's interactive confirmation prompt.

        --init-upgrade and --init-reconfigure require --init.
        """
        if init_upgrade and not init:
            raise ValueError("--init-upgrade requires --init")
        if init_reconfigure and not init:
            raise ValueError("--init-reconfigure requires --init")

        command_params = CommandParams(context=context)
        init_params = (
            InitParams(upgrade=init_upgrade, reconfigure=init_reconfigure)
            if init
            else None
        )

        with ExitStack() as stack:
            if aws_profiles_path is not None and aws_profile is not None:
                _ = stack.enter_context(
                    aws_environ(profiles_path=aws_profiles_path, profile=aws_profile)
                )

            terraform_backend_destroy(
                binary_cache_path=binary_cache_path,
                command_params=command_params,
                module_path=module_path,
                backend_status_path=backend_status_path,
                init_on_entry=init,
                init_params=init_params,
                destroy_params=DestroyParams(auto_approve=destroy_auto_approve),
            )

    return cast(Task[Callable[[Context, bool, bool, bool, bool], None]], task_destroy)

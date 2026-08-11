"""Generic tasks for applying and destroying a Terraform configuration."""

import pathlib
from contextlib import ExitStack
from typing import Callable, cast

from invoke.context import Context
from invoke.tasks import Task, task

from fogies.terraform.backend import BackendConfig
from fogies.tools.aws_environ import AwsEnvironContextManager
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    TfbackendContextManager,
    TfvarsContextManager,
    terraform,
)


def get_task_apply(
    *,
    binary_cache_path: pathlib.Path,
    module_path: pathlib.Path,
    aws_environ: AwsEnvironContextManager | None = None,
    backend: BackendConfig | None = None,
    backend_status_path: pathlib.Path | None = None,
    tfbackend: TfbackendContextManager | None = None,
    tfvars: TfvarsContextManager | None = None,
    default_init: bool = True,
    default_init_upgrade: bool = False,
    default_init_reconfigure: bool = False,
    default_apply_auto_approve: bool = False,
) -> Task[Callable[[Context, bool, bool, bool, bool], None]]:
    if backend is not None and tfbackend is None:
        raise ValueError("tfbackend is required when backend is set")
    if (backend_status_path is None) != (backend is None):
        raise ValueError("backend_status_path and backend must be provided together")

    @task(name="apply")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_apply(
        context: Context,
        init: bool = default_init,
        init_upgrade: bool = default_init_upgrade,
        init_reconfigure: bool = default_init_reconfigure,
        apply_auto_approve: bool = default_apply_auto_approve,
    ) -> None:
        """
        Apply a Terraform configuration.

        Flags:
          --init                Run terraform init before apply (downloads providers, sets up backend).
          --init-upgrade        Pass -upgrade to init; checks for newer provider versions within constraints.
          --init-reconfigure    Pass -reconfigure to init; re-initializes backend from scratch.
          --apply-auto-approve  Skip Terraform's interactive confirmation prompt.

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
            if aws_environ is not None:
                _ = stack.enter_context(aws_environ)

            tfbackend_path = stack.enter_context(tfbackend) if tfbackend else None
            tfvars_path = stack.enter_context(tfvars) if tfvars else None

            _ = stack.enter_context(
                terraform(
                    binary_cache_path=binary_cache_path,
                    command_params=command_params,
                    module_path=module_path,
                    backend=backend,
                    backend_status_path=backend_status_path,
                    tfbackend_path=tfbackend_path,
                    tfvars_path=tfvars_path,
                    init_on_entry=init,
                    init_params=init_params,
                    apply_on_entry=True,
                    apply_params=ApplyParams(auto_approve=apply_auto_approve),
                    destroy_on_exit=False,
                )
            )

    return cast(Task[Callable[[Context, bool, bool, bool, bool], None]], task_apply)


def get_task_destroy(
    *,
    binary_cache_path: pathlib.Path,
    module_path: pathlib.Path,
    aws_environ: AwsEnvironContextManager | None = None,
    backend: BackendConfig | None = None,
    backend_status_path: pathlib.Path | None = None,
    tfbackend: TfbackendContextManager | None = None,
    tfvars: TfvarsContextManager | None = None,
    default_init: bool = True,
    default_init_upgrade: bool = False,
    default_init_reconfigure: bool = False,
    default_destroy_auto_approve: bool = False,
) -> Task[Callable[[Context, bool, bool, bool, bool], None]]:
    if backend is not None and tfbackend is None:
        raise ValueError("tfbackend is required when backend is set")
    if (backend_status_path is None) != (backend is None):
        raise ValueError("backend_status_path and backend must be provided together")

    @task(name="destroy")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_destroy(
        context: Context,
        init: bool = default_init,
        init_upgrade: bool = default_init_upgrade,
        init_reconfigure: bool = default_init_reconfigure,
        destroy_auto_approve: bool = default_destroy_auto_approve,
    ) -> None:
        """
        Destroy a Terraform configuration.

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
            if aws_environ is not None:
                _ = stack.enter_context(aws_environ)

            tfbackend_path = stack.enter_context(tfbackend) if tfbackend else None
            tfvars_path = stack.enter_context(tfvars) if tfvars else None

            _ = stack.enter_context(
                terraform(
                    binary_cache_path=binary_cache_path,
                    command_params=command_params,
                    module_path=module_path,
                    backend=backend,
                    backend_status_path=backend_status_path,
                    tfbackend_path=tfbackend_path,
                    tfvars_path=tfvars_path,
                    init_on_entry=init,
                    init_params=init_params,
                    destroy_on_exit=True,
                    destroy_params=DestroyParams(auto_approve=destroy_auto_approve),
                )
            )

    return cast(Task[Callable[[Context, bool, bool, bool, bool], None]], task_destroy)

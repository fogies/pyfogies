"""Generic tasks for applying and destroying a Terraform configuration."""

import pathlib
from contextlib import ExitStack
from typing import Callable, cast

from invoke.context import Context
from invoke.tasks import Task, task

from fogies.terraform.backend import BackendConfigS3
from fogies.tools.aws_environ import aws_environ
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    TerraformOutputModel,
    terraform,
    terraform_output,
    terraform_tfbackend_s3,
)


def get_task_apply(
    *,
    module_path: pathlib.Path,
    binary_cache_path: pathlib.Path,
    staging_path: pathlib.Path | None = None,
    aws_profiles_path: pathlib.Path | None = None,
    aws_profile: str | None = None,
    backend: BackendConfigS3 | None = None,
    default_init: bool = True,
    default_init_upgrade: bool = False,
    default_init_reconfigure: bool = False,
    default_apply_auto_approve: bool = False,
    default_output: bool = False,
    output_model: type[TerraformOutputModel],
) -> Task[Callable[[Context, bool, bool, bool, bool, bool], None]]:
    if backend is not None and staging_path is None:
        raise ValueError("staging_path is required when backend is set")

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
        Apply a Terraform configuration.

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

            tfbackend_path = None
            if backend is not None:
                assert staging_path is not None
                tfbackend_path = stack.enter_context(
                    terraform_tfbackend_s3(
                        path=staging_path / "terraform.s3.tfbackend",
                        backend=backend,
                    )
                )

            output_result = stack.enter_context(
                terraform_output(
                    binary_cache_path=binary_cache_path,
                    command_params=command_params,
                    module_path=module_path,
                    tfbackend_path=tfbackend_path,
                    init_on_entry=init,
                    init_params=init_params,
                    apply_on_entry=True,
                    apply_params=ApplyParams(auto_approve=apply_auto_approve),
                    destroy_on_exit=False,
                    output_model=output_model,
                )
            )

            if output:
                print(output_result.model_dump_json(indent=2))

    return cast(
        Task[Callable[[Context, bool, bool, bool, bool, bool], None]], task_apply
    )


def get_task_destroy(
    *,
    module_path: pathlib.Path,
    binary_cache_path: pathlib.Path,
    staging_path: pathlib.Path | None = None,
    aws_profiles_path: pathlib.Path | None = None,
    aws_profile: str | None = None,
    backend: BackendConfigS3 | None = None,
    default_init: bool = True,
    default_init_upgrade: bool = False,
    default_init_reconfigure: bool = False,
    default_destroy_auto_approve: bool = False,
) -> Task[Callable[[Context, bool, bool, bool, bool], None]]:
    if backend is not None and staging_path is None:
        raise ValueError("staging_path is required when backend is set")

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
            if aws_profiles_path is not None and aws_profile is not None:
                _ = stack.enter_context(
                    aws_environ(profiles_path=aws_profiles_path, profile=aws_profile)
                )

            tfbackend_path = None
            if backend is not None:
                assert staging_path is not None
                tfbackend_path = stack.enter_context(
                    terraform_tfbackend_s3(
                        path=staging_path / "terraform.s3.tfbackend",
                        backend=backend,
                    )
                )

            tf = stack.enter_context(
                terraform(
                    binary_cache_path=binary_cache_path,
                    command_params=command_params,
                    module_path=module_path,
                    tfbackend_path=tfbackend_path,
                    init_on_entry=init,
                    init_params=init_params,
                )
            )

            _ = tf.destroy(
                command_params=command_params,
                module_path=module_path,
                destroy_params=DestroyParams(auto_approve=destroy_auto_approve),
            )

    return cast(Task[Callable[[Context, bool, bool, bool, bool], None]], task_destroy)

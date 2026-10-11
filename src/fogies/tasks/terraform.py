"""Generic tasks for applying and destroying a Terraform configuration."""

import pathlib
from contextlib import ExitStack
from typing import Callable, cast

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task

from fogies.terraform.backend import BackendConfig
from fogies.tools.aws_environ import AwsEnvironFactory
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    TfbackendFactory,
    TfvarsFactory,
    terraform,
)


def validate_init_params(*, init: bool, init_params: InitParams) -> None:
    """Raise ValueError for task flags that cannot be given together.

    The init options only apply when init runs, and Terraform does not allow
    migrating state while also reconfiguring the backend.
    """
    if init_params.migrate_state and not init:
        raise ValueError("--init-migrate-state requires --init")
    if init_params.reconfigure and not init:
        raise ValueError("--init-reconfigure requires --init")
    if init_params.upgrade and not init:
        raise ValueError("--init-upgrade requires --init")
    if init_params.migrate_state and init_params.reconfigure:
        raise ValueError(
            "--init-migrate-state and --init-reconfigure cannot be combined"
        )


def get_task_apply(
    *,
    binary_cache_path: pathlib.Path,
    module_path: pathlib.Path,
    aws_environ_factory: AwsEnvironFactory | None = None,
    backend_config: BackendConfig | None = None,
    backend_status_path: pathlib.Path | None = None,
    tfbackend_factory: TfbackendFactory | None = None,
    tfvars_factory: TfvarsFactory | None = None,
    default_init: bool = True,
    default_init_migrate_state: bool = False,
    default_init_reconfigure: bool = False,
    default_init_upgrade: bool = False,
    default_apply_auto_approve: bool = False,
) -> Task[Callable[[Context, bool, bool, bool, bool, bool], None]]:
    if backend_config is not None and tfbackend_factory is None:
        raise ValueError("tfbackend_factory is required when backend_config is set")
    if (backend_config is not None or tfbackend_factory is not None) and (
        aws_environ_factory is None
    ):
        raise ValueError(
            "aws_environ_factory is required when backend_config or tfbackend_factory is set"
        )
    if (backend_status_path is None) != (backend_config is None):
        raise ValueError(
            "backend_status_path and backend_config must be provided together"
        )

    @task(
        name="apply",
        auto_shortflags=False,
        help={
            "init": "Include terraform init. Skip with --no-init.",
            "init_migrate_state": "During init, migrate state to a changed backend.",
            "init_reconfigure": "During init, reconfigure the backend.",
            "init_upgrade": "During init, upgrade providers.",
            "apply_auto_approve": "Skip interactive confirmation.",
        },
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_apply(
        context: Context,
        init: bool = default_init,
        init_migrate_state: bool = default_init_migrate_state,
        init_reconfigure: bool = default_init_reconfigure,
        init_upgrade: bool = default_init_upgrade,
        apply_auto_approve: bool = default_apply_auto_approve,
    ) -> None:
        """
        Apply a Terraform configuration.
        """
        init_params = InitParams(
            migrate_state=init_migrate_state,
            reconfigure=init_reconfigure,
            upgrade=init_upgrade,
        )
        validate_init_params(init=init, init_params=init_params)

        command_params = CommandParams(context=context)

        with ExitStack() as stack:
            aws_environ = (
                stack.enter_context(aws_environ_factory())
                if aws_environ_factory
                else None
            )

            tfbackend_path = (
                stack.enter_context(tfbackend_factory(aws_environ))
                if tfbackend_factory and aws_environ
                else None
            )
            tfvars_path = (
                stack.enter_context(tfvars_factory()) if tfvars_factory else None
            )

            _ = stack.enter_context(
                terraform(
                    binary_cache_path=binary_cache_path,
                    command_params=command_params,
                    module_path=module_path,
                    backend_config=backend_config,
                    aws_environ=aws_environ,
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

    return cast(
        Task[Callable[[Context, bool, bool, bool, bool, bool], None]], task_apply
    )


def get_task_destroy(
    *,
    binary_cache_path: pathlib.Path,
    module_path: pathlib.Path,
    aws_environ_factory: AwsEnvironFactory | None = None,
    backend_config: BackendConfig | None = None,
    backend_status_path: pathlib.Path | None = None,
    tfbackend_factory: TfbackendFactory | None = None,
    tfvars_factory: TfvarsFactory | None = None,
    default_init: bool = True,
    default_init_migrate_state: bool = False,
    default_init_reconfigure: bool = False,
    default_init_upgrade: bool = False,
    default_destroy_auto_approve: bool = False,
) -> Task[Callable[[Context, bool, bool, bool, bool, bool], None]]:
    if backend_config is not None and tfbackend_factory is None:
        raise ValueError("tfbackend_factory is required when backend_config is set")
    if (backend_config is not None or tfbackend_factory is not None) and (
        aws_environ_factory is None
    ):
        raise ValueError(
            "aws_environ_factory is required when backend_config or tfbackend_factory is set"
        )
    if (backend_status_path is None) != (backend_config is None):
        raise ValueError(
            "backend_status_path and backend_config must be provided together"
        )

    @task(
        name="destroy",
        auto_shortflags=False,
        help={
            "init": "Include terraform init. Skip with --no-init.",
            "init_migrate_state": "During init, migrate state to a changed backend.",
            "init_reconfigure": "During init, reconfigure the backend.",
            "init_upgrade": "During init, upgrade providers.",
            "destroy_auto_approve": "Skip interactive confirmation.",
        },
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_destroy(
        context: Context,
        init: bool = default_init,
        init_migrate_state: bool = default_init_migrate_state,
        init_reconfigure: bool = default_init_reconfigure,
        init_upgrade: bool = default_init_upgrade,
        destroy_auto_approve: bool = default_destroy_auto_approve,
    ) -> None:
        """
        Destroy a Terraform configuration.
        """
        init_params = InitParams(
            migrate_state=init_migrate_state,
            reconfigure=init_reconfigure,
            upgrade=init_upgrade,
        )
        validate_init_params(init=init, init_params=init_params)

        command_params = CommandParams(context=context)

        with ExitStack() as stack:
            aws_environ = (
                stack.enter_context(aws_environ_factory())
                if aws_environ_factory
                else None
            )

            tfbackend_path = (
                stack.enter_context(tfbackend_factory(aws_environ))
                if tfbackend_factory and aws_environ
                else None
            )
            tfvars_path = (
                stack.enter_context(tfvars_factory()) if tfvars_factory else None
            )

            _ = stack.enter_context(
                terraform(
                    binary_cache_path=binary_cache_path,
                    command_params=command_params,
                    module_path=module_path,
                    backend_config=backend_config,
                    aws_environ=aws_environ,
                    backend_status_path=backend_status_path,
                    tfbackend_path=tfbackend_path,
                    tfvars_path=tfvars_path,
                    init_on_entry=init,
                    init_params=init_params,
                    destroy_on_exit=True,
                    destroy_params=DestroyParams(auto_approve=destroy_auto_approve),
                )
            )

    return cast(
        Task[Callable[[Context, bool, bool, bool, bool, bool], None]], task_destroy
    )


def get_collection(
    *,
    collection_name: str,
    binary_cache_path: pathlib.Path,
    module_path: pathlib.Path,
    aws_environ_factory: AwsEnvironFactory | None = None,
    backend_config: BackendConfig | None = None,
    backend_status_path: pathlib.Path | None = None,
    tfbackend_factory: TfbackendFactory | None = None,
    tfvars_factory: TfvarsFactory | None = None,
) -> Collection:
    """Get a collection of tasks for applying and destroying a Terraform configuration."""
    collection = Collection(collection_name)
    collection.add_task(
        get_task_apply(
            binary_cache_path=binary_cache_path,
            module_path=module_path,
            aws_environ_factory=aws_environ_factory,
            backend_config=backend_config,
            backend_status_path=backend_status_path,
            tfbackend_factory=tfbackend_factory,
            tfvars_factory=tfvars_factory,
        )
    )
    collection.add_task(
        get_task_destroy(
            binary_cache_path=binary_cache_path,
            module_path=module_path,
            aws_environ_factory=aws_environ_factory,
            backend_config=backend_config,
            backend_status_path=backend_status_path,
            tfbackend_factory=tfbackend_factory,
            tfvars_factory=tfvars_factory,
        )
    )
    return collection

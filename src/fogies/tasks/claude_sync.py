"""Tasks for setting up and running claude-sync."""

import pathlib
from collections.abc import Callable
from typing import cast

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task

from fogies.tools.claude_sync import claude_sync, configure_claude_sync
from fogies.tools.command import CommandParams


def get_task_configure(
    *,
    binary_cache_path: pathlib.Path,
    claude_sync_config_path: pathlib.Path,
    aws_config_path: pathlib.Path,
) -> Task[Callable[..., None]]:
    @task(
        name="configure",
        auto_shortflags=False,
        help={
            "force": "Force overwrite based on current configuration.",
        },
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_configure(context: Context, force: bool = False) -> None:
        """
        Configure claude-sync on this machine.
        """
        setup = configure_claude_sync(
            claude_sync_config_path=claude_sync_config_path,
            aws_config_path=aws_config_path,
            force=force,
        )

        if setup.generated_age_key:
            print("Generated encryption key.")
        if setup.applied_to_claude_sync_files:
            print("Applied configuration to claude-sync files.")
        else:
            print("Already configured.")

        # Reads from the bucket and changes nothing, so this fails now, and
        # clearly, if the credentials, bucket or key are wrong.
        print("Checking the connection:")
        with claude_sync(
            binary_cache_path=binary_cache_path, raise_if_env_exists=False
        ) as cs:
            _ = cs.pull(command_params=CommandParams(context=context), dry_run=True)

    return cast(Task[Callable[..., None]], task_configure)


def get_task_conflicts(*, binary_cache_path: pathlib.Path) -> Task[Callable[..., None]]:
    @task(
        name="conflicts",
        auto_shortflags=False,
        help={
            "keep": "Resolve all conflicts, keeping 'local' or 'remote'.",
            "list": "Only list the conflicts.",
        },
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_conflicts(
        context: Context, keep: str | None = None, list_: bool = False
    ) -> None:
        """
        Resolve conflicts from a sync.
        """
        if keep not in (None, "local", "remote"):
            raise ValueError("--keep must be 'local' or 'remote'")
        if keep is not None and list_:
            raise ValueError("--keep and --list cannot be combined")

        with claude_sync(
            binary_cache_path=binary_cache_path, raise_if_env_exists=False
        ) as cs:
            command_params = CommandParams(context=context)
            if list_:
                _ = cs.list_conflicts(command_params=command_params)
            else:
                _ = cs.resolve_conflicts(command_params=command_params, keep=keep)

    return cast(Task[Callable[..., None]], task_conflicts)


def get_task_pull(
    *,
    binary_cache_path: pathlib.Path,
    default_dry_run: bool = False,
    default_force: bool = False,
) -> Task[Callable[..., None]]:
    @task(
        name="pull",
        auto_shortflags=False,
        help={
            "dry_run": "Show what would be downloaded.",
            "force": "Force overwrite of local files.",
        },
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_pull(
        context: Context,
        dry_run: bool = default_dry_run,
        force: bool = default_force,
    ) -> None:
        """
        Download remote changes.
        """
        with claude_sync(
            binary_cache_path=binary_cache_path, raise_if_env_exists=False
        ) as cs:
            _ = cs.pull(
                command_params=CommandParams(context=context),
                dry_run=dry_run,
                force=force,
            )

    return cast(Task[Callable[..., None]], task_pull)


def get_task_push(*, binary_cache_path: pathlib.Path) -> Task[Callable[..., None]]:
    @task(
        name="push", auto_shortflags=False
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_push(context: Context) -> None:
        """
        Upload local changes.
        """
        with claude_sync(
            binary_cache_path=binary_cache_path, raise_if_env_exists=False
        ) as cs:
            _ = cs.push(command_params=CommandParams(context=context))

    return cast(Task[Callable[..., None]], task_push)


def get_task_status(*, binary_cache_path: pathlib.Path) -> Task[Callable[..., None]]:
    @task(
        name="status", auto_shortflags=False
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_status(context: Context) -> None:
        """
        Show local changes since prior synchronization.
        """
        with claude_sync(
            binary_cache_path=binary_cache_path, raise_if_env_exists=False
        ) as cs:
            _ = cs.status(command_params=CommandParams(context=context))

    return cast(Task[Callable[..., None]], task_status)


def get_task_sync(*, binary_cache_path: pathlib.Path) -> Task[Callable[..., None]]:
    @task(
        name="sync", auto_shortflags=False
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_sync(context: Context) -> None:
        """
        Pull, resolve any conflicts, then push.
        """
        with claude_sync(
            binary_cache_path=binary_cache_path, raise_if_env_exists=False
        ) as cs:
            try:
                cs.sync(command_params=CommandParams(context=context))
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc

    return cast(Task[Callable[..., None]], task_sync)


def get_collection(
    *,
    collection_name: str,
    binary_cache_path: pathlib.Path,
    claude_sync_config_path: pathlib.Path,
    aws_config_path: pathlib.Path,
) -> Collection:
    """Get a collection of tasks for setting up and running claude-sync."""
    collection = Collection(collection_name)
    collection.add_task(
        get_task_configure(
            binary_cache_path=binary_cache_path,
            claude_sync_config_path=claude_sync_config_path,
            aws_config_path=aws_config_path,
        )
    )
    collection.add_task(get_task_conflicts(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_pull(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_push(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_status(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_sync(binary_cache_path=binary_cache_path))
    return collection

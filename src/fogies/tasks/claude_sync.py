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
    *, binary_cache_path: pathlib.Path, secrets_claude_sync_path: pathlib.Path
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
            secrets_path=secrets_claude_sync_path, force=force
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


def get_task_pull(*, binary_cache_path: pathlib.Path) -> Task[Callable[..., None]]:
    @task(
        name="pull",
        auto_shortflags=False,
        help={
            "dry_run": "Show what would be downloaded.",
            "force": "Force overwrite of local files.",
        },
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_pull(context: Context, dry_run: bool = False, force: bool = False) -> None:
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


def get_collection(
    *,
    collection_name: str,
    binary_cache_path: pathlib.Path,
    secrets_claude_sync_path: pathlib.Path,
) -> Collection:
    """Get a collection of tasks for setting up and running claude-sync."""
    collection = Collection(collection_name)
    collection.add_task(
        get_task_configure(
            binary_cache_path=binary_cache_path,
            secrets_claude_sync_path=secrets_claude_sync_path,
        )
    )
    collection.add_task(get_task_pull(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_push(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_status(binary_cache_path=binary_cache_path))
    return collection

"""Tasks for setting up and running claude-sync, and deleting sessions it syncs."""

import pathlib
from collections.abc import Callable
from typing import cast

from claude_agent_sdk import list_sessions
from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task

from fogies.tasks.terminal import spawn_new_terminal
from fogies.tools.aws_environ import aws_environ_from_config
from fogies.tools.claude_code import describe_session, find_session_id
from fogies.tools.claude_sync import (
    claude_sync,
    configure_claude_sync,
    is_first_pull,
    load_claude_sync_config,
)
from fogies.tools.claude_sync_deletions import apply_deletions, delete_everywhere
from fogies.tools.claude_sync_watch import is_watching, watch_and_sync
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
            command_params = CommandParams(context=context)
            _ = cs.pull(command_params=command_params, dry_run=True)

            # What was just shown is what the first pull does, which merges with
            # what is here, and it is followed by a push of what is only here.
            if is_first_pull():
                try:
                    answer = input("Run the first sync now? [y/N] ")
                except EOFError:
                    answer = ""
                if answer.strip().lower() == "y":
                    try:
                        cs.sync(command_params=command_params)
                    except ValueError as exc:
                        raise SystemExit(str(exc)) from exc
                else:
                    print("Run the sync task when ready.")

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


def get_task_delete(
    *, claude_sync_config_path: pathlib.Path, aws_config_path: pathlib.Path
) -> Task[Callable[..., None]]:
    @task(
        name="delete",
        auto_shortflags=False,
        help={
            "session_id": "Session to delete, from any part of its ID that is only in that one.",
        },
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_delete(context: Context, session_id: str) -> None:
        """
        Delete a session from this machine, and from every other that syncs.
        """
        _ = context
        sessions = {session.session_id: session for session in list_sessions()}
        delete_id = find_session_id(list(sessions), session_id)

        print(describe_session(sessions[delete_id]))
        print("Its transcript is deleted from this machine now, and from each other")
        print("machine when it next syncs. These tasks cannot get it back.")
        if input("Delete it everywhere? [y/N] ").strip().lower() != "y":
            print("Not deleted.")
            return

        config = load_claude_sync_config(path=claude_sync_config_path)
        with aws_environ_from_config(
            config_path=aws_config_path,
            profile_name=config.aws_profile,
            raise_if_env_exists=False,
        ):
            delete_everywhere(
                bucket_name=config.bucket, region=config.region, session_id=delete_id
            )
        print("Deleted {}.".format(delete_id))

    return cast(Task[Callable[..., None]], task_delete)


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


def get_task_sync(
    *,
    binary_cache_path: pathlib.Path,
    claude_sync_config_path: pathlib.Path,
    aws_config_path: pathlib.Path,
) -> Task[Callable[..., None]]:
    @task(
        name="sync",
        auto_shortflags=False,
        help={
            "watch": "Keep syncing, in a new terminal, until stopped. Never asks about conflicts, and waits for them to be resolved. The first sync on a machine has to be run without it.",
        },
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_sync(context: Context, watch: bool = False) -> None:
        """
        Pull, resolve any conflicts, delete what other machines deleted, then push.
        """
        # Before a new terminal, so that this one says it.
        if watch and is_first_pull():
            raise SystemExit(
                "This machine has not synced before. Run the sync task without --watch first."
            )

        if watch and is_watching():
            raise SystemExit(
                "claude-sync is already being watched, in another terminal."
            )

        if watch and not spawn_new_terminal(context):
            return

        with claude_sync(
            binary_cache_path=binary_cache_path, raise_if_env_exists=False
        ) as cs:

            def delete_what_others_deleted() -> None:
                config = load_claude_sync_config(path=claude_sync_config_path)
                with aws_environ_from_config(
                    config_path=aws_config_path,
                    profile_name=config.aws_profile,
                    raise_if_env_exists=False,
                ):
                    deleted = apply_deletions(
                        bucket_name=config.bucket, region=config.region
                    )
                if deleted:
                    print(
                        "Deleted {} session(s) that other machines deleted: {}".format(
                            len(deleted), ", ".join(deleted)
                        )
                    )

            def sync_once() -> None:
                cs.sync(
                    command_params=CommandParams(context=context),
                    unattended=watch,
                    after_pull=delete_what_others_deleted,
                )

            if watch:
                try:
                    watch_and_sync(sync=sync_once)
                except KeyboardInterrupt:
                    print("Stopped.")
                except ValueError as exc:
                    raise SystemExit(str(exc)) from exc
            else:
                try:
                    sync_once()
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
    """Get a collection of tasks for setting up and running claude-sync, and deleting sessions it syncs."""
    collection = Collection(collection_name)
    collection.add_task(
        get_task_configure(
            binary_cache_path=binary_cache_path,
            claude_sync_config_path=claude_sync_config_path,
            aws_config_path=aws_config_path,
        )
    )
    collection.add_task(get_task_conflicts(binary_cache_path=binary_cache_path))
    collection.add_task(
        get_task_delete(
            claude_sync_config_path=claude_sync_config_path,
            aws_config_path=aws_config_path,
        )
    )
    collection.add_task(get_task_pull(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_push(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_status(binary_cache_path=binary_cache_path))
    collection.add_task(
        get_task_sync(
            binary_cache_path=binary_cache_path,
            claude_sync_config_path=claude_sync_config_path,
            aws_config_path=aws_config_path,
        )
    )
    return collection

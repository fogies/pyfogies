"""Tasks for signing in to Claude Code, and for its sessions.

Sessions are listed and deleted with the Claude Agent SDK. See
<https://code.claude.com/docs/en/agent-sdk/python>.
"""

import pathlib
from collections.abc import Callable
from typing import cast

from claude_agent_sdk import delete_session, list_sessions
from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task

from fogies.tools.claude_code import (
    claude_code,
    describe_session,
    find_session_id,
)


def get_task_login(*, binary_cache_path: pathlib.Path) -> Task[Callable[..., None]]:
    @task(
        name="login", auto_shortflags=False
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_login(context: Context) -> None:
        """
        Login to Claude Code.
        """
        _ = context
        with claude_code(binary_cache_path=binary_cache_path) as cc:
            cc.auth_login()

    return cast(Task[Callable[..., None]], task_login)


def get_task_logout(*, binary_cache_path: pathlib.Path) -> Task[Callable[..., None]]:
    @task(
        name="logout", auto_shortflags=False
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_logout(context: Context) -> None:
        """
        Logout of Claude Code.
        """
        _ = context
        with claude_code(binary_cache_path=binary_cache_path) as cc:
            cc.auth_logout()

    return cast(Task[Callable[..., None]], task_logout)


def get_task_status(*, binary_cache_path: pathlib.Path) -> Task[Callable[..., None]]:
    @task(
        name="status", auto_shortflags=False
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_status(context: Context) -> None:
        """
        Show login status of Claude Code.
        """
        _ = context
        with claude_code(binary_cache_path=binary_cache_path) as cc:
            if not cc.auth_status():
                print("Not signed in. Sign in with the login task.")

    return cast(Task[Callable[..., None]], task_status)


def get_task_sessions() -> Task[Callable[..., None]]:
    @task(
        name="sessions", auto_shortflags=False
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_sessions(context: Context) -> None:
        """
        List sessions on this machine.
        """
        _ = context
        for session in list_sessions():
            print(describe_session(session))

    return cast(Task[Callable[..., None]], task_sessions)


def get_task_delete() -> Task[Callable[..., None]]:
    @task(
        name="delete",
        auto_shortflags=False,
        help={
            "session_id": "Session to delete, from any part of its ID that is only in that one.",
        },
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_delete(context: Context, session_id: str) -> None:
        """
        Delete a session from this machine, permanently.
        """
        _ = context
        sessions = {session.session_id: session for session in list_sessions()}
        delete_id = find_session_id(list(sessions), session_id)

        print(describe_session(sessions[delete_id]))
        print("Its transcript is deleted from this machine, and cannot be recovered.")
        if input("Delete it? [y/N] ").strip().lower() != "y":
            print("Not deleted.")
            return

        delete_session(delete_id)
        print("Deleted {}.".format(delete_id))

    return cast(Task[Callable[..., None]], task_delete)


def get_collection(
    *,
    collection_name: str,
    binary_cache_path: pathlib.Path,
    include_delete: bool,
) -> Collection:
    """Get a collection of tasks for signing in to Claude Code, and for its sessions.

    *include_delete* adds a task that deletes a session from this machine. It
    is not for where sessions are synced (e.g., by claude-sync), as a session
    deleted on one machine comes back from the others. Delete them in a way
    that syncing knows about.
    """
    collection = Collection(collection_name)
    if include_delete:
        collection.add_task(get_task_delete())
    collection.add_task(get_task_login(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_logout(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_sessions())
    collection.add_task(get_task_status(binary_cache_path=binary_cache_path))
    return collection

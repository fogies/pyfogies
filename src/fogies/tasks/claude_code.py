"""Tasks for signing in to Claude Code, and for its sessions.

Sessions are listed with the Claude Agent SDK. See
<https://code.claude.com/docs/en/agent-sdk/python>.
"""

import pathlib
from collections.abc import Callable
from typing import cast

from claude_agent_sdk import list_sessions
from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task

from fogies.tools.claude_code import claude_code, describe_session


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


def get_collection(
    *,
    collection_name: str,
    binary_cache_path: pathlib.Path,
) -> Collection:
    """Get a collection of tasks for signing in to Claude Code, and for its sessions.

    There is no task to delete a session. Where sessions are synced (e.g., by
    claude-sync), one deleted on a machine comes back from the others, unless it
    is deleted in a way that syncing knows about.
    """
    collection = Collection(collection_name)
    collection.add_task(get_task_login(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_logout(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_sessions())
    collection.add_task(get_task_status(binary_cache_path=binary_cache_path))
    return collection

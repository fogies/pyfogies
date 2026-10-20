"""Tasks for signing in to Claude Code and resuming its sessions in the desktop app.

Sessions are listed and found with the Claude Agent SDK. See
<https://code.claude.com/docs/en/agent-sdk/python>.
"""

import datetime
import pathlib
from collections.abc import Callable
from typing import cast

from claude_agent_sdk import get_session_info, list_sessions
from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task

from fogies.tools.claude_code import claude_code

# Longest title shown in a list of sessions.
_TITLE_LENGTH = 60


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
            # The transcript's modified time. For a session synced from another
            # machine (e.g., by claude-sync), that is when it was synced.
            modified = (
                datetime.datetime.fromtimestamp(session.last_modified / 1000)
                .astimezone()
                .strftime("%Y-%m-%d %H:%M")
            )
            project = pathlib.Path(session.cwd).name if session.cwd is not None else "?"
            title = " ".join((session.summary or "").split())
            if len(title) > _TITLE_LENGTH:
                title = title[: _TITLE_LENGTH - 3] + "..."
            print(
                "{}  {}  {:<24}  {}".format(
                    session.session_id,
                    modified,
                    project,
                    title,
                )
            )

    return cast(Task[Callable[..., None]], task_sessions)


def get_task_resume(*, binary_cache_path: pathlib.Path) -> Task[Callable[..., None]]:
    @task(
        name="resume",
        auto_shortflags=False,
        help={
            "session_id": "Session to resume, as listed by sessions.",
        },
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_resume(context: Context, session_id: str) -> None:
        """
        Resume a session in Claude desktop.
        """
        _ = context
        session = get_session_info(session_id)
        if session is None:
            raise ValueError("No session '{}'".format(session_id))
        if session.cwd is None:
            raise ValueError(
                "Session '{}' has no recorded directory".format(session_id)
            )
        with claude_code(binary_cache_path=binary_cache_path) as cc:
            cc.resume_in_desktop(session_id=session_id, cwd=pathlib.Path(session.cwd))

    return cast(Task[Callable[..., None]], task_resume)


def get_collection(
    *,
    collection_name: str,
    binary_cache_path: pathlib.Path,
) -> Collection:
    """Get a collection of tasks for signing in to Claude Code and resuming its sessions."""
    collection = Collection(collection_name)
    collection.add_task(get_task_login(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_logout(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_resume(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_sessions())
    collection.add_task(get_task_status(binary_cache_path=binary_cache_path))
    return collection

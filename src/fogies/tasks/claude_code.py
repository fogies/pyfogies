"""Tasks for signing in to Claude Code."""

import pathlib
from collections.abc import Callable
from typing import cast

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task

from fogies.tools.claude_code import claude_code


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


def get_collection(
    *,
    collection_name: str,
    binary_cache_path: pathlib.Path,
) -> Collection:
    """Get a collection of tasks for signing in to Claude Code."""
    collection = Collection(collection_name)
    collection.add_task(get_task_login(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_logout(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_status(binary_cache_path=binary_cache_path))
    return collection

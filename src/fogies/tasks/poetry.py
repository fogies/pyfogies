"""
Tasks for building and publishing with Poetry.
"""

import tomllib
from pathlib import Path
from typing import Callable, cast

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task


@task(name="build")  # pyright: ignore[reportUntypedFunctionDecorator]
def _task_build_impl(context: Context) -> None:
    """
    Build package artifacts.
    """
    _ = context.run(
        command=" ".join(
            [
                "poetry",
                "build",
            ]
        ),
        echo=True,
    )


def _task_publish_get(*, path_secrets_poetry: Path) -> Task[Callable[[Context], None]]:
    """
    Get a task that publishes package artifacts.
    """

    @task(name="publish")  # pyright: ignore[reportUntypedFunctionDecorator]
    def _task_publish_impl(context: Context) -> None:
        """
        Publish package to PyPI.
        """
        with path_secrets_poetry.open("rb") as handle:
            secrets_poetry = tomllib.load(handle)

        api_key: str = cast(str, secrets_poetry["api"]["api_key"])

        _ = context.run(
            command=" ".join(
                [
                    "poetry",
                    "publish",
                    "--dry-run",
                    "--username {}".format("__token__"),
                    "--password {}".format(api_key),
                ]
            ),
            echo=True,
        )

    return cast(Task[Callable[[Context], None]], _task_publish_impl)


def get_collection(path_secrets_poetry: Path) -> Collection:
    """
    Get a collection of tasks.
    """
    namespace = Collection("poetry")

    # Explicitly type the decorated functions.
    task_build: Task[Callable[[Context], None]] = cast(
        Task[Callable[[Context], None]],
        _task_build_impl,
    )
    task_publish = _task_publish_get(path_secrets_poetry=path_secrets_poetry)

    namespace.add_task(task_build)
    namespace.add_task(task_publish)

    return namespace

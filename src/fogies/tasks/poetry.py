"""
Tasks for building and publishing with Poetry.
"""

import tomllib
from pathlib import Path
from typing import Callable, cast

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task


def get_task_build() -> Task[Callable[[Context], None]]:
    @task(name="build")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_build(context: Context) -> None:
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

    return cast(Task[Callable[[Context], None]], task_build)


def get_task_publish(*, path_secrets_poetry: Path) -> Task[Callable[[Context], None]]:
    @task(name="publish")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_publish(context: Context) -> None:
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

    return cast(Task[Callable[[Context], None]], task_publish)


def get_collection(path_secrets_poetry: Path) -> Collection:
    """
    Get a collection of tasks.
    """
    namespace = Collection("poetry")

    task_build = get_task_build()
    task_publish = get_task_publish(path_secrets_poetry=path_secrets_poetry)

    namespace.add_task(task_build)
    namespace.add_task(task_publish)

    return namespace

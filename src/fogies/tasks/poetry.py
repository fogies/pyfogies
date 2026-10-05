"""
Tasks for building and publishing with Poetry.
"""

import tomllib
from pathlib import Path
from typing import Callable, cast

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task

from fogies.templates import ensure_from_template, poetry_toml_template_factory


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


def get_task_publish(*, secrets_poetry_path: Path) -> Task[Callable[[Context], None]]:
    @task(name="publish")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_publish(context: Context) -> None:
        """
        Publish package to PyPI.
        """
        ensure_from_template(
            path=secrets_poetry_path, template_factory=poetry_toml_template_factory
        )

        with secrets_poetry_path.open("rb") as handle:
            secrets_poetry = tomllib.load(handle)

        api_key: str = cast(str, secrets_poetry["pypi"]["api_key"])

        # Read the PyPI token from the environment,
        # so it is not echoed to the terminal as exposed to other processes.
        _ = context.run(
            command=" ".join(
                [
                    "poetry",
                    "publish",
                ]
            ),
            echo=True,
            env={"POETRY_PYPI_TOKEN_PYPI": api_key},
        )

    return cast(Task[Callable[[Context], None]], task_publish)


def get_collection(*, secrets_poetry_path: Path) -> Collection:
    """
    Get a collection of tasks.
    """
    namespace = Collection("poetry")

    task_build = get_task_build()
    task_publish = get_task_publish(secrets_poetry_path=secrets_poetry_path)

    namespace.add_task(task_build)
    namespace.add_task(task_publish)

    return namespace

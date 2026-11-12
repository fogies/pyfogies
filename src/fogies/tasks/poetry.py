"""
Tasks for building and publishing with Poetry.
"""

from pathlib import Path
from typing import Callable, cast

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task
from pydantic import BaseModel

from fogies.config import load_config
from fogies.templates import poetry_toml_template_factory


class _PypiConfig(BaseModel):
    api_key: str


class _PoetryConfig(BaseModel):
    pypi: _PypiConfig


def get_task_build() -> Task[Callable[[Context], None]]:
    @task(
        name="build", auto_shortflags=False
    )  # pyright: ignore[reportUntypedFunctionDecorator]
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
    @task(
        name="publish", auto_shortflags=False
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_publish(context: Context) -> None:
        """
        Publish package to PyPI.
        """
        poetry_config = load_config(
            path=secrets_poetry_path,
            model=_PoetryConfig,
            template_factory=poetry_toml_template_factory,
        )
        api_key = poetry_config.pypi.api_key

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

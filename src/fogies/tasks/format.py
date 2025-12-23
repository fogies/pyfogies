"""
Tasks for applying code formatting.
"""

from typing import Callable, cast

from invoke.context import Context
from invoke.tasks import Task, task


def get_task_format() -> Task[Callable[[Context], None]]:
    @task(name="format")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_format(context: Context) -> None:
        """
        Apply code formatting.
        """
        _ = context.run(
            command=" ".join(
                [
                    "isort",
                    ".",
                ]
            ),
            echo=True,
        )

        _ = context.run(
            command=" ".join(
                [
                    "black",
                    ".",
                ]
            ),
            echo=True,
        )

    return cast(Task[Callable[[Context], None]], task_format)

"""
Tasks for running linting.
"""

from typing import Callable, cast

from invoke.context import Context
from invoke.tasks import Task, task


def get_task_lint() -> Task[Callable[[Context], None]]:
    @task(name="lint")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_lint(context: Context) -> None:
        """
        Run linting.
        """
        _ = context.run(
            command=" ".join(
                [
                    "basedpyright",
                    ".",
                ]
            ),
            echo=True,
        )

    return cast(Task[Callable[[Context], None]], task_lint)

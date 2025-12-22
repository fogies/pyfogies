"""
Task for applying code formatting.
"""

from typing import Callable, cast

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task


@task(name="format")  # pyright: ignore[reportUntypedFunctionDecorator]
def _task_format_impl(context: Context) -> None:
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


# Explicitly type the decorated function.
task_format: Task[Callable[[Context], None]] = cast(
    Task[Callable[[Context], None]],
    _task_format_impl,
)


class FormatTasks:
    """
    Tasks for applying code formatting.
    """

    def get_collection(self) -> Collection:
        """
        Get a collection of tasks.
        """
        namespace = Collection("format")
        namespace.add_task(task_format)

        return namespace

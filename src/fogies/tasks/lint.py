"""
Task for running linting.
"""

from typing import Callable, cast

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task


@task(name="lint")  # pyright: ignore[reportUntypedFunctionDecorator]
def _task_lint_impl(context: Context) -> None:
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


# Explicitly type the decorated function.
task_lint: Task[Callable[[Context], None]] = cast(
    Task[Callable[[Context], None]],
    _task_lint_impl,
)


class LintTasks:
    """
    Tasks for running linting.
    """

    def get_collection(self) -> Collection:
        """
        Get a collection of tasks.
        """
        namespace = Collection("lint")
        namespace.add_task(task_lint)

        return namespace

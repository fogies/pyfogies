"""
Task for running tests.
"""

import os
import shutil

from typing import Callable, cast

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task


@task(name="test")  # pyright: ignore[reportUntypedFunctionDecorator]
def _task_test_impl(context: Context) -> None:
    """
    Run tests.
    """
    # Explicitly set COLUMNS environment variable to match terminal width.
    # Without this, execution through invoke will use a narrow default width.
    env = os.environ.copy()
    env["COLUMNS"] = str(shutil.get_terminal_size().columns)

    _ = context.run(
        command=" ".join(
            [
                "pytest",
                # Explicitly enable color output.
                # Without this, output through invoke will not be in color.
                "--color=yes",
                ".",
            ]
        ),
        echo=True,
        env=env,
    )


# Explicitly type the decorated function.
task_test: Task[Callable[[Context], None]] = cast(
    Task[Callable[[Context], None]],
    _task_test_impl,
)


class TestTasks:
    """
    Tasks for running tests.
    """

    def get_collection(self) -> Collection:
        """
        Get a collection of tasks.
        """
        namespace = Collection("test")
        namespace.add_task(task_test)

        return namespace

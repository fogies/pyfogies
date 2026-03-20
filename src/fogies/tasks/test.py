"""
Tasks for running tests.
"""

import os
import shutil
from typing import Callable, cast

from invoke.context import Context
from invoke.tasks import Task, task


def get_task_test(path_tests: str | None = None) -> Task[Callable[[Context], None]]:
    @task(name="test")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_test(context: Context) -> None:
        """
        Run tests.
        """
        # Explicitly set COLUMNS environment variable to match terminal width.
        # Without this, execution through invoke will use a narrow default width.
        env = os.environ.copy()
        env["COLUMNS"] = str(shutil.get_terminal_size().columns)

        # Default to current directory.
        param_path_tests = path_tests if path_tests is not None else "."

        _ = context.run(
            command=" ".join(
                [
                    "pytest",
                    # Explicitly enable color output.
                    # Without this, output through invoke will not be in color.
                    "--color=yes",
                    param_path_tests,
                ]
            ),
            echo=True,
            env=env,
        )

    return cast(Task[Callable[[Context], None]], task_test)

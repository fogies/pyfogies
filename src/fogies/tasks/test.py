"""
Task for running tests.
"""

import os
import shutil

from invoke import Collection, task


class TestTasks:
    """
    Tasks for running tests.
    """

    @task(name="test")
    def task_test(context) -> None:
        """
        Run tests.
        """
        # Explicitly set COLUMNS environment variable to match terminal width.
        # Without this, execution through invoke will use a narrow default width.
        env = os.environ.copy()
        env["COLUMNS"] = str(shutil.get_terminal_size().columns)

        context.run(
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

    def get_collection(self) -> Collection:
        """
        Get a collection of tasks.
        """
        namespace = Collection("test")
        namespace.add_task(self.task_test)

        return namespace

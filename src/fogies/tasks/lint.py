"""
Task for running linting.
"""

from invoke import Collection, task


class LintTasks:
    """
    Tasks for running linting.
    """

    @task(name="lint")
    def task_lint(context):
        """
        Run linting.
        """

        context.run(
            command=" ".join(
                [
                    "basedpyright",
                    ".",
                ]
            ),
            echo=True,
        )

    def get_collection(self) -> Collection:
        """
        Get a collection of tasks.
        """
        namespace = Collection("lint")
        namespace.add_task(self.task_lint)

        return namespace
